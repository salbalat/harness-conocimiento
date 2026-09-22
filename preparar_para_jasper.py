#!/usr/bin/env python3
"""Prepara las fichas del harness para Jasper, sin tocar las 16 hechas a mano.

Qué hace:
  - arregla `section` (quita el «· fragmento N»: eso es para mostrar, no para localizar)
  - quita las citas duplicadas que deja el solape del troceo
  - marca cada ficha con `verified_by: "harness"` para que Jasper sepa de dónde viene
  - comprueba que la ficha resultante SÍ encuentra su sección y que el sha256 casa

Salida: harness_cards.json (fichero aparte: verified_cards.json no se toca).
"""
import hashlib, json, re, unicodedata
from pathlib import Path

RAIZ = Path("/home/perrix/harness-conocimiento")


# Copiado LITERAL de Jasper (`yoga_retrieval.py:17`, función `words`), porque
# `candidates()` compara los topics de la ficha contra la salida de esa función.
# Si los topics no están normalizados igual, la ficha no se encuentra nunca:
# el topic «haṭha yoga» jamás casa con el token «hatha».
STOP = set('de del la las los el un una que como para por con en y a me quiero sobre '
           'what the of and to is i how'.split())


def words(text):
    norm = "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z]+", norm) if len(w) > 2 and w not in STOP]


def sin_espacios(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("—", "-").replace("–", "-").replace("…", "...")
    return re.sub(r"\s+", "", t).lower().strip()


content = json.loads((RAIZ / "corpus" / "sections.json").read_text(encoding="utf-8"))

# Todas las fuentes: cada pasada del harness y las rescatadas de la cola (su cita ya
# había pasado la puerta de código; lo que se reescribió fue la respuesta).
fichas = []
for patron in ("fichas/fichas-*.json", "fichas/rescatadas-*.json"):
    for ruta in sorted(RAIZ.glob(patron)):
        fichas.extend(json.loads(ruta.read_text(encoding="utf-8")))

# El paratexto que se apartó leyéndolo a mano no vuelve a entrar. Se excluye por la
# CITA, no por el id: los ids se recalculan aquí abajo y no serían los mismos.
descartes = RAIZ / "descartadas_paratexto.json"
fuera = set()
if descartes.exists():
    fuera = {sin_espacios(f["evidence"])
             for f in json.loads(descartes.read_text(encoding="utf-8"))}

salida, vistas = [], set()
sin_seccion = duplicadas = sha_mal = apartadas = 0

for f in fichas:
    # 1. `section` sin el sufijo de fragmento
    seccion_loc = re.sub(r"\s*·\s*fragmento\s+\d+\s*$", "", f.get("section", ""))
    f = {**f, "section": seccion_loc}

    # 2. ¿existe esa sección?
    sec = next((s for s in content
                if s["book"] == f["book"] and s["locator"] == seccion_loc), None)
    if sec is None:
        sin_seccion += 1
        continue

    # 3. sha256 contra la sección real
    if f.get("section_sha256") != hashlib.sha256(sec["text"].encode()).hexdigest():
        sha_mal += 1
        continue

    # 4. duplicados por el solape, y el paratexto apartado a mano
    clave = (f["book"], sin_espacios(f["evidence"]))
    if clave[1] in fuera:
        apartadas += 1
        continue
    if clave in vistas:
        duplicadas += 1
        continue
    vistas.add(clave)

    # 5. topics normalizados como los normaliza Jasper, o no se encuentran
    tp, vistos_tp = [], set()
    for t in f.get("topics", []) or []:
        for w in words(str(t)):
            if w not in vistos_tp:
                vistos_tp.add(w)
                tp.append(w)
    f["topics"] = tp

    # 6. id determinista: el del harness es un número de orden dentro de SU pasada, así
    #    que al juntar varias pasadas dos fichas distintas pueden compartirlo. Jasper
    #    resuelve las fichas por id (`render`), y un id repetido serviría la ficha
    #    equivocada. Con la huella de la cita es único y estable entre regeneraciones.
    f["id"] = f'{f["book"]}_{hashlib.sha256(clave[1].encode()).hexdigest()[:10]}'

    # 7. procedencia explícita
    f["verified_by"] = "harness"
    f["reviewed"] = False          # se mantiene: el harness no firma por Salvador
    salida.append(f)

destino = RAIZ / "harness_cards.json"
destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

print("=" * 60)
print("FICHAS PREPARADAS PARA JASPER")
print("=" * 60)
print(f"entraban                       : {len(fichas)}")
print(f"  sin sección que las respalde : -{sin_seccion}")
print(f"  sha256 que no casa           : -{sha_mal}")
print(f"  paratexto apartado a mano    : -{apartadas}")
print(f"  duplicadas por el solape     : -{duplicadas}")
print(f"SALEN                          : {len(salida)}")
ids = [f["id"] for f in salida]
print(f"ids únicos                     : {len(set(ids))} de {len(ids)}"
      f"{'  <-- ¡COLISIÓN!' if len(set(ids)) != len(ids) else ''}")
print(f"\nescrito en {destino}")
