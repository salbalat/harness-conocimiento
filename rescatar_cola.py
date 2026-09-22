#!/usr/bin/env python3
"""Rescata las fichas de la cola reescribiendo la respuesta.

Por qué se pueden rescatar: su CITA ya pasó la puerta de código, así que es literal
del libro. Lo que falló fue la respuesta: 172 de 206 se rechazaron porque añadía cosas
que la cita no dice. El modelo las añadía porque veía el PASAJE ENTERO y se traía
contexto de fuera de la cita.

El arreglo: en el rescate el modelo ve SOLO LA CITA. Si no tiene el pasaje delante,
no puede añadir lo que no está. Después se vuelve a cribar con el modelo severo.

Uso:  python3 rescatar_cola.py [--limite N]
"""
import argparse, json, time
from pathlib import Path

from harness import (COLA, FICHAS, LOGS, MODELO_CRIBADOR, MODELO_PROPONEDOR,
                     P_CRIBAR, json_del_modelo, normalizar, ollama)

P_RESCATE = """Tienes UNA cita literal de un libro. Escribe una ficha basada SOLO en ella.

REGLA ABSOLUTA: no puedes mencionar NADA que no esté en la cita. Ni nombres propios,
ni cifras, ni escuelas, ni conceptos, ni contexto histórico. Si la cita no lo dice,
no existe. Prefiere quedarte corto a añadir una palabra de más.

- "answer": 1-3 frases en español explicando lo que dice la cita. Nada más.
- "question": la pregunta que esa respuesta contesta.
- Si la cita por sí sola no da para nada útil, devuelve {{"util": false}}.

CITA:
\"\"\"
{evidence}
\"\"\"

Devuelve SOLO este JSON:
{{"util": true, "question": "...", "answer": "..."}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--cola", default="cola-20260920-091748.json")
    args = ap.parse_args()

    fichas = json.loads((COLA / args.cola).read_text(encoding="utf-8"))
    if args.limite:
        fichas = fichas[:args.limite]

    marca = time.strftime("%Y%m%d-%H%M%S")
    f_ok = FICHAS / f"rescatadas-{marca}.json"
    f_no = COLA / f"irrecuperables-{marca}.json"
    f_log = LOGS / f"rescate-{marca}.txt"

    rescatadas, perdidas = [], []
    t0 = time.time()
    print(f"Rescate · {len(fichas)} fichas de la cola")
    print(f"  la cita ya está verificada; se reescribe SOLO la respuesta\n", flush=True)

    with f_log.open("w", encoding="utf-8") as log:
        for i, f in enumerate(fichas, 1):
            ev = f.get("evidence", "")
            estado, detalle = "perdida", ""
            try:
                bruto = ollama(MODELO_PROPONEDOR, P_RESCATE.format(evidence=ev))
                prop = json_del_modelo(bruto)
                if not prop or not prop.get("util", True):
                    detalle = "la cita sola no da para ficha"
                else:
                    answer = (prop.get("answer") or "").strip()
                    if not answer:
                        detalle = "sin respuesta"
                    else:
                        bruto2 = ollama(MODELO_CRIBADOR,
                                        P_CRIBAR.format(evidence=ev, answer=answer))
                        crib = json_del_modelo(bruto2) or {}
                        if crib.get("valida"):
                            nueva = dict(f)
                            nueva["answer"] = answer
                            nueva["question"] = (prop.get("question") or f.get("question", "")).strip()
                            nueva["harness"] = {**f.get("harness", {}),
                                                "veredicto": True,
                                                "motivo": str(crib.get("motivo", ""))[:200],
                                                "rescatada": True}
                            rescatadas.append(nueva)
                            estado, detalle = "RESCATADA", str(crib.get("motivo", ""))[:70]
                        else:
                            detalle = f"sigue sin pasar: {str(crib.get('motivo',''))[:60]}"
            except Exception as e:
                detalle = f"fallo: {e}"

            if estado == "perdida":
                perdidas.append(f)
            linea = f"[{i}/{len(fichas)}] {estado:10s} {f.get('book','?'):10s} {detalle}"
            print(linea, flush=True)
            log.write(linea + "\n")
            log.flush()

            if i % 10 == 0:
                f_ok.write_text(json.dumps(rescatadas, ensure_ascii=False, indent=2), encoding="utf-8")

    f_ok.write_text(json.dumps(rescatadas, ensure_ascii=False, indent=2), encoding="utf-8")
    f_no.write_text(json.dumps(perdidas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"rescatadas: {len(rescatadas)} de {len(fichas)}   "
          f"({100*len(rescatadas)//max(len(fichas),1)}%)")
    print(f"tiempo: {(time.time()-t0)/60:.1f} min")
    print(f"-> {f_ok}")


if __name__ == "__main__":
    main()
