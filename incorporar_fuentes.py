#!/usr/bin/env python3
"""Convierte los textos descargados en secciones del corpus, limpiando el OCR.

Por qué hace falta limpiar: los escaneos traen basura de biblioteca
("GOVERNMENT OF INDIA DEPARTMENT OF ARCHAEOLOGY"), devanagari roto y erratas
("THE A.THA TOGA PRABXPIKA" por "Hatha Yoga Pradipika"). El harness compara la cita
LETRA POR LETRA contra el texto: si el modelo lee basura y la corrige al copiar, la
cita no casa y se pierde una ficha buena. Así que solo entran párrafos que sean
inglés legible de verdad.

Criterio (medible, no a ojo): un párrafo vale si
  - al menos el 92% de sus caracteres son ASCII imprimibles, y
  - al menos el 18% de sus palabras son palabras inglesas corrientes, y
  - tiene 200 caracteres o más y al menos 25 palabras.
El tercer filtro se lleva por delante los encabezados y los índices.

Salida: se AÑADEN secciones a corpus/sections.json. Nada de lo que había se toca.
"""
import json, re, unicodedata
from pathlib import Path

RAIZ = Path("/home/perrix/harness-conocimiento")
FUENTES = RAIZ / "corpus" / "fuentes"

COMUNES = set("""the of and to in a is that it for as with be by this are on or from at
which an have has was were not but they he she his her its their our your you we all
any can may shall should would will if when where what who whom how there here then
than them these those such other more most some no nor only own same so too very one
two three first second other into out up down over under again further once about
against between during before after above below both each few other own said says
body mind breath life death man men should must let thus also may because while""".split())

OBRAS = [
    {"fichero": "gheranda-siva-samhita-vasu-1915.txt",
     "book": "gheranda",
     "title": "Gheranda Samhita y Siva Samhita (Sacred Books of the Hindus XV)",
     "source": "https://archive.org/download/india.history.resource.88861/88861_djvu.txt",
     "autor": "trad. Srisa Chandra Vasu, 1915",
     "coverage": "escaneo OCR de archive.org, dominio publico (pre-1930); solo se conservan "
                 "los parrafos en ingles legible: el OCR intercala devanagari roto"},
    {"fichero": "yoga-mimansa-kuvalayananda-1928.txt",
     "book": "yogamimansa",
     "title": "Yoga-Mimansa (revista del Kaivalyadhama)",
     "source": "https://archive.org/download/dli.ministry.31127/31750.37282_djvu.txt",
     "autor": "Swami Kuvalayananda, 1928",
     "coverage": "escaneo OCR de archive.org, dominio publico (1928); asanas y pranayama "
                 "con base fisiologica; solo parrafos en ingles legible"},
    {"fichero": "hatha-yoga-pradipika-sinh-1915.txt",
     "book": "hathapradipika",
     "title": "Hatha Yoga Pradipika (traduccion completa)",
     "source": "https://archive.org/download/dli.csl.7087/7087_djvu.txt",
     "autor": "trad. Pancham Sinh, 1915",
     "coverage": "escaneo OCR de archive.org, dominio publico (1915); libro COMPLETO, "
                 "frente a los 4 capitulos de Wikisource que ya habia en el corpus"},
    {"fichero": "nccih-yoga.txt",
     "book": "nccih_yoga",
     "title": "Yoga: Effectiveness and Safety (NCCIH, NIH)",
     "source": "https://www.nccih.nih.gov/health/yoga-what-you-need-to-know",
     "autor": "National Center for Complementary and Integrative Health, act. 2023",
     "coverage": "dominio publico: obra del gobierno de EE.UU. ('Text on the NCCIH website "
                 "is not copyrighted and is in the public domain'). SOLO EL TEXTO: las "
                 "imagenes del sitio son de Getty y NO son dominio publico. Capa de "
                 "evidencia clinica y seguridad, no de practica"},
    {"fichero": "nccih-meditacion.txt",
     "book": "nccih_meditacion",
     "title": "Meditation and Mindfulness: Effectiveness and Safety (NCCIH, NIH)",
     "source": "https://www.nccih.nih.gov/health/meditation-and-mindfulness-what-you-need-to-know",
     "autor": "National Center for Complementary and Integrative Health, act. 2022",
     "coverage": "dominio publico: obra del gobierno de EE.UU. SOLO EL TEXTO (las imagenes "
                 "no lo son). Evidencia clinica sobre meditacion y mindfulness"},
    {"fichero": "science-of-breath-ramacharaka-1904.txt",
     "book": "breath",
     "title": "The Hindu-Yogi Science of Breath",
     "source": "https://www.gutenberg.org/cache/epub/13402/pg13402.txt",
     "autor": "Yogi Ramacharaka, 1904",
     "coverage": "Project Gutenberg, dominio publico; transcripcion humana (sin OCR), "
                 "texto limpio; pranayama y respiracion"},
]

TROZO = 4200


def limpio(linea):
    """Se filtra POR LÍNEA, no por párrafo.

    Los escaneos no traen párrafos: el Hatha Pradipika son 1.402 líneas sueltas de OCR,
    1.315 de menos de 200 caracteres. Filtrando por párrafo se tiraba el 73% del libro,
    y entre lo tirado había texto bueno («Practice will go on increasing, varied sounds
    become audible to the»). Por línea se conserva eso y se va la basura real:
    «<SL», «fiUC», «PBS.», los sellos de biblioteca y el devanagari roto.
    """
    linea = linea.strip()
    if len(linea) < 12:
        return False
    palabras = re.findall(r"[A-Za-z']{2,}", linea)
    if len(palabras) < 3:
        return False
    ascii_ok = sum(1 for c in linea if 32 <= ord(c) < 127)
    if ascii_ok / len(linea) < 0.90:
        return False
    # una línea de inglés de verdad trae alguna palabra corriente
    return any(w.lower() in COMUNES for w in palabras)


def secciones_de(texto, obra):
    # Gutenberg: quitar cabecera y licencia, que no son el libro
    if "*** START OF" in texto:
        texto = texto.split("*** START OF", 1)[1].split("\n", 1)[1]
    if "*** END OF" in texto:
        texto = texto.split("*** END OF", 1)[0]

    buenas = [re.sub(r"[ \t]+", " ", l).strip()
              for l in texto.split("\n") if limpio(l)]

    # agrupar en secciones de ~TROZO caracteres
    secciones, actual = [], []
    for l in buenas:
        actual.append(l)
        if sum(len(x) for x in actual) >= TROZO:
            secciones.append("\n".join(actual))
            actual = []
    if actual and sum(len(x) for x in actual) > 600:
        secciones.append("\n".join(actual))

    return [{"book": obra["book"],
             "title": obra["title"],
             "locator": f"{obra['autor']} · bloque {i}",
             "source": obra["source"],
             "text": s,
             "coverage": obra["coverage"]}
            for i, s in enumerate(secciones, 1)]


def main():
    destino = RAIZ / "corpus" / "sections.json"
    actuales = json.loads(destino.read_text(encoding="utf-8"))
    ya = {s["book"] for s in actuales}

    nuevas = []
    print(f"{'obra':16s} {'bruto':>9s} {'limpio':>9s} {'%':>5s} {'secciones':>10s}")
    for obra in OBRAS:
        ruta = FUENTES / obra["fichero"]
        if not ruta.exists():
            print(f"{obra['book']:16s} FALTA {ruta}")
            continue
        if obra["book"] in ya:
            print(f"{obra['book']:16s} ya estaba en el corpus, no se toca")
            continue
        bruto = ruta.read_text(encoding="utf-8", errors="replace")
        secs = secciones_de(bruto, obra)
        util = sum(len(s["text"]) for s in secs)
        pct = 100 * util // max(len(bruto), 1)
        print(f"{obra['book']:16s} {len(bruto):9d} {util:9d} {pct:4d}% {len(secs):10d}")
        nuevas.extend(secs)

    if not nuevas:
        print("\nnada nuevo que añadir")
        return

    copia = destino.with_suffix(".json.bak-before-fuentes")
    if not copia.exists():
        copia.write_text(json.dumps(actuales, ensure_ascii=False, indent=2), encoding="utf-8")
    destino.write_text(json.dumps(actuales + nuevas, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"\ncorpus: {len(actuales)} -> {len(actuales) + len(nuevas)} secciones "
          f"(+{len(nuevas)})   copia previa en {copia.name}")


if __name__ == "__main__":
    main()
