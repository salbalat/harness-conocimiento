#!/usr/bin/env python3
"""Harness de conocimiento: convierte secciones de libros en fichas citables.

Regla que sostiene todo: la cita (`evidence`) se comprueba LETRA POR LETRA contra el
texto original POR CÓDIGO, no por un modelo. Un modelo no puede colar una cita falsa.

Flujo por sección:
  1. Modelo A (proponedor) devuelve JSON con evidence/answer/topics/question.
  2. El código comprueba que `evidence` está literal en el texto. Si no, se cae.
  3. Modelo B (cribador, distinto de A) juzga si `answer` se sostiene SOLO con esa cita.
  4. Se calcula section_sha256 y se escribe la ficha con el contrato de Jasper.
  5. Lo dudoso va a cola/ para revisión humana.

Uso:
  python3 harness.py --limite 10            # prueba corta
  python3 harness.py                        # las 502
  python3 harness.py --solo-libro hatha     # un libro concreto
"""
import argparse, hashlib, json, os, re, sys, time, unicodedata, urllib.error, urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CORPUS = RAIZ / "corpus"
FICHAS = RAIZ / "fichas"
COLA = RAIZ / "cola"
LOGS = RAIZ / "logs"

# Donde escucha Ollama. Orden: variable OLLAMA_URL, fichero .ollama-url, localhost.
# defecto es localhost; en esta maquina la direccion real vive en .ollama-url,
_url_local = RAIZ / ".ollama-url"      # fichero de cada maquina, fuera del repo
OLLAMA = (os.environ.get("OLLAMA_URL")
          or (_url_local.read_text(encoding="utf-8").strip() if _url_local.exists() else None)
          or "http://127.0.0.1:11434")
MODELO_PROPONEDOR = "qwen2.5:14b"
MODELO_CRIBADOR = "mistral-small:24b"   # distinto de A: si fuera el mismo, se daría la razón

TIEMPO_LIMITE = 240


# ---------------------------------------------------------------- utilidades

def normalizar(t):
    """Para comparar citas. Quita acentos, comillas tipográficas y TODOS los espacios.

    Por qué sin espacios: los PDF del corpus están mal extraídos. Hay títulos con las
    letras separadas ("I a m  f o r e v e r"), palabras partidas por el guionado
    ("le arned") y saltos de línea dentro de las frases. El modelo lee eso y copia la
    cita bien escrita, que es lo correcto; comparando carácter a carácter con espacios
    se rechazaban citas verdaderas.

    Sigue siendo prueba sólida: que 40+ caracteres seguidos coincidan sin espacios es
    imposible por azar. Lo que ya no puede hacer el modelo es INVENTARSE la frase.

    NO se usa para guardar: la ficha conserva la cita legible que devolvió el modelo.
    """
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("—", "-").replace("–", "-").replace("…", "...")
    t = re.sub(r"\s+", "", t)          # fuera todos los espacios
    return t.lower().strip()


def ollama(modelo, prompt, formato_json=True):
    cuerpo = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 900},
    }
    if formato_json:
        cuerpo["format"] = "json"
    datos = json.dumps(cuerpo).encode()
    req = urllib.request.Request(
        OLLAMA + "/api/generate", data=datos,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIEMPO_LIMITE) as r:
        return json.loads(r.read())["response"]


def json_del_modelo(bruto):
    """Los modelos a veces envuelven el JSON en texto. Se rescata el primer objeto."""
    try:
        return json.loads(bruto)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", bruto, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- los prompts

P_PROPONER = """Eres un documentalista. Lee el PASAJE y extrae UNA ficha.

REGLAS ESTRICTAS:
- "evidence" debe ser una frase COPIADA LITERALMENTE del pasaje, carácter por carácter.
  Entre 40 y 300 caracteres. NO la traduzcas, NO la resumas, NO la corrijas.
- "answer" explica en español qué dice el autor en ese pasaje, en 2-4 frases.
  Debe sostenerse SOLO con la cita. No añadas datos de fuera del pasaje.
- "question" es la pregunta que esta ficha responde.
- "topics" son 4-8 palabras clave en español, minúsculas, sin acentos.
- Si el pasaje no da para una ficha útil, devuelve {{"util": false}}.

OBRA: {obra}
PASAJE:
\"\"\"
{texto}
\"\"\"

Devuelve SOLO este JSON:
{{"util": true, "question": "...", "evidence": "...", "answer": "...", "topics": ["..."]}}"""

P_CRIBAR = """Eres un revisor severo. Decide si la RESPUESTA se sostiene ÚNICAMENTE con la CITA.

Rechaza (valida=false) si la respuesta:
- afirma algo que la cita no dice,
- añade datos, cifras o nombres ausentes de la cita,
- cambia el sentido o exagera lo que dice el autor,
- da consejo médico o instrucciones que la cita no respalda.

Acepta (valida=true) solo si todo lo que afirma la respuesta está en la cita.

CITA (literal del libro):
\"\"\"
{evidence}
\"\"\"

RESPUESTA A REVISAR:
\"\"\"
{answer}
\"\"\"

Devuelve SOLO este JSON:
{{"valida": true/false, "motivo": "una frase breve"}}"""


# ---------------------------------------------------------------- el proceso

def procesar(seccion, indice):
    """Devuelve (estado, ficha_o_none, detalle). estado: ok | cola | descarte."""
    texto = seccion.get("text", "")
    obra = seccion.get("title") or seccion.get("book", "?")

    if len(texto.strip()) < 200:
        return "descarte", None, "pasaje demasiado corto"

    # --- 1. proponer
    try:
        pista = ""
        if seccion.get("_foco"):
            pista = ("\nEste pasaje nombra: " + ", ".join(seccion["_foco"])
                     + ". Si dice algo sobre esa postura, la ficha DEBE ir sobre ella "
                     + "y la pregunta debe nombrarla.")
        bruto = ollama(MODELO_PROPONEDOR,
                       P_PROPONER.format(obra=obra, texto=texto[:6000]) + pista)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return "descarte", None, f"fallo del proponedor: {e}"

    prop = json_del_modelo(bruto)
    if not prop:
        return "descarte", None, "el proponedor no devolvió JSON"
    if not prop.get("util", True):
        return "descarte", None, "el modelo lo marcó como no útil"

    evidence = (prop.get("evidence") or "").strip()
    answer = (prop.get("answer") or "").strip()
    if not evidence or not answer:
        return "descarte", None, "faltan evidence o answer"

    # --- 2. LA PUERTA: la cita debe estar literal en el original. Esto lo decide
    #        el código, no un modelo. Es lo que hace imposible inventarse una cita.
    if normalizar(evidence) not in normalizar(texto):
        return "descarte", None, f"cita NO literal: «{evidence[:70]}…»"

    if len(evidence) < 25:
        return "descarte", None, "cita demasiado corta para ser prueba"

    # --- 3. cribar con un modelo distinto
    try:
        bruto2 = ollama(MODELO_CRIBADOR, P_CRIBAR.format(evidence=evidence, answer=answer))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return "cola", None, f"el cribador falló ({e}): a revisión humana"

    crib = json_del_modelo(bruto2)
    if crib is None:
        return "cola", None, "el cribador no devolvió JSON: a revisión humana"

    ficha = {
        "id": f"{seccion.get('book','x')}_{indice:04d}",
        "book": seccion.get("book", ""),
        "title": obra,
        "book_title": seccion.get("title", ""),
        "book_author": seccion.get("source", ""),
        # `section` localiza la sección en sections.json: debe ser el locator ORIGINAL,
        # sin el «· fragmento N», o Jasper no la encuentra y tira la ficha.
        "section": seccion.get("_locator_seccion", seccion.get("locator", "")),
        "locator": seccion.get("locator", ""),   # este sí lleva el fragmento: es lo que se muestra
        "evidence": evidence,
        "answer": answer,
        "question": (prop.get("question") or "").strip(),
        "topics": [str(t).lower() for t in (prop.get("topics") or [])][:8],
        "reviewed": False,
        # Lo que mira verified_answers para dejarla entrar: sin esto, la ficha
        # pasa el harness y el agente la descarta igualmente.
        "verified_by": "harness",
        "review_date": time.strftime("%Y-%m-%d"),
        # sha256 de la SECCIÓN COMPLETA (no del fragmento): así la ficha se sigue
        # cayendo sola si el texto original cambia, igual que en Jasper.
        "section_sha256": hashlib.sha256(
            seccion.get("_texto_seccion", texto).encode()).hexdigest(),
        "harness": {
            "proponedor": MODELO_PROPONEDOR,
            "cribador": MODELO_CRIBADOR,
            "veredicto": bool(crib.get("valida")),
            "motivo": str(crib.get("motivo", ""))[:200],
        },
    }

    if crib.get("valida"):
        return "ok", ficha, "cita literal + cribador conforme"
    return "cola", ficha, f"cribador la rechaza: {crib.get('motivo','')}"


TROZO = 5000      # caracteres por fragmento
SOLAPE = 400      # para no cortar una idea justo en el borde


def trocear(secciones):
    """Parte las secciones largas en fragmentos.

    El corpus es muy desigual: Frankl trae secciones de ~1.100 caracteres, pero
    Hatha Yoga Pradípika son 4 CAPÍTULOS de ~45.000 y `safety` una pieza de 66.886.
    Sin trocear se sacaría una sola ficha de cada capítulo, tirando el resto del libro.

    El `section_sha256` se sigue calculando sobre el texto de la SECCIÓN COMPLETA,
    para no romper el mecanismo de Jasper que descarta fichas si el original cambia.
    """
    salida = []
    for s in secciones:
        t = s.get("text", "")
        if len(t) <= TROZO:
            salida.append(s)
            continue
        paso = TROZO - SOLAPE
        for n, i in enumerate(range(0, len(t), paso), 1):
            frag = t[i:i + TROZO]
            if len(frag) < 600:
                break
            copia = dict(s)
            copia["text"] = frag
            copia["_texto_seccion"] = t          # para el sha256
            copia["_fragmento"] = n
            loc = s.get("locator", "")
            copia["_locator_seccion"] = loc      # el de verdad, para que Jasper encuentre la sección
            copia["locator"] = f"{loc} · fragmento {n}" if loc else f"fragmento {n}"
            salida.append(copia)
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="procesar solo N secciones")
    ap.add_argument("--solo-libro", default="", help="filtrar por campo book")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--foco", help="JSON de terminos: solo pasajes que los nombren")
    ap.add_argument("--sin-trocear", action="store_true")
    args = ap.parse_args()

    secciones = json.loads((CORPUS / "sections.json").read_text(encoding="utf-8"))
    if args.solo_libro:
        secciones = [s for s in secciones if s.get("book") == args.solo_libro]
    if not args.sin_trocear:
        antes = len(secciones)
        secciones = trocear(secciones)
        print(f"troceado: {antes} secciones -> {len(secciones)} fragmentos")
    # Con --foco solo se miran los pasajes que nombran alguno de los terminos, y se
    # apunta cual: sin esa pista el proponedor escribe la ficha de lo que le parece,
    # y aqui lo que se busca es la ficha DE esa postura.
    if args.foco:
        terminos = json.loads(Path(args.foco).read_text(encoding="utf-8"))
        patrones = [(n, re.compile(pat, re.I)) for n, pat in terminos.items()]
        con_foco = []
        for s in secciones:
            vistos = [n for n, rx in patrones if rx.search(s["text"])]
            if vistos:
                con_foco.append({**s, "_foco": vistos[:3]})
        print(f"foco: {len(secciones)} secciones -> {len(con_foco)} que nombran alguna")
        secciones = con_foco
    secciones = secciones[args.desde:]
    if args.limite:
        secciones = secciones[:args.limite]

    marca = time.strftime("%Y%m%d-%H%M%S")
    f_ok, f_cola = FICHAS / f"fichas-{marca}.json", COLA / f"cola-{marca}.json"
    f_log = LOGS / f"log-{marca}.txt"

    aprobadas, dudosas, descartes = [], [], 0
    t0 = time.time()

    print(f"Harness · {len(secciones)} secciones")
    print(f"  proponedor: {MODELO_PROPONEDOR}")
    print(f"  cribador:   {MODELO_CRIBADOR}")
    print(f"  puerta:     cita literal comprobada por código\n", flush=True)

    with f_log.open("w", encoding="utf-8") as log:
        for i, s in enumerate(secciones, 1):
            estado, ficha, detalle = procesar(s, args.desde + i)
            linea = f"[{i}/{len(secciones)}] {estado:8s} {s.get('book','?'):10s} {detalle[:90]}"
            print(linea, flush=True)
            log.write(linea + "\n")
            log.flush()

            if estado == "ok":
                aprobadas.append(ficha)
            elif estado == "cola" and ficha:
                dudosas.append(ficha)
            else:
                descartes += 1

            if i % 10 == 0:
                f_ok.write_text(json.dumps(aprobadas, ensure_ascii=False, indent=2), encoding="utf-8")
                f_cola.write_text(json.dumps(dudosas, ensure_ascii=False, indent=2), encoding="utf-8")

    f_ok.write_text(json.dumps(aprobadas, ensure_ascii=False, indent=2), encoding="utf-8")
    f_cola.write_text(json.dumps(dudosas, ensure_ascii=False, indent=2), encoding="utf-8")

    mins = (time.time() - t0) / 60
    print(f"\n{'='*60}")
    print(f"aprobadas: {len(aprobadas)}   a revisar: {len(dudosas)}   descartadas: {descartes}")
    print(f"tiempo: {mins:.1f} min")
    print(f"fichas -> {f_ok}")
    print(f"cola   -> {f_cola}")


if __name__ == "__main__":
    sys.exit(main())
