#!/usr/bin/env python3
"""Auditoría INDEPENDIENTE de las fichas del harness.

No se fía de lo que dice el harness: vuelve a comprobar cada ficha contra el
corpus original, por código, y compara con las 16 fichas hechas a mano.
"""
import hashlib, json, re, unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path("/home/perrix/harness-conocimiento")


def normalizar(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("—", "-").replace("–", "-").replace("…", "...")
    return re.sub(r"\s+", "", t).lower().strip()


secciones = json.loads((RAIZ / "corpus" / "sections.json").read_text(encoding="utf-8"))
manuales = json.loads((RAIZ / "corpus" / "verified_cards.json").read_text(encoding="utf-8"))

# índice: texto normalizado de cada sección, y sha256 -> sección
textos_norm = [normalizar(s.get("text", "")) for s in secciones]
por_sha = {hashlib.sha256(s.get("text", "").encode()).hexdigest(): s for s in secciones}

fichas = json.loads((RAIZ / "fichas" / "fichas-20260920-091748.json").read_text(encoding="utf-8"))

cita_ok = cita_mal = sha_ok = sha_mal = 0
malas = []
for f in fichas:
    ev = normalizar(f.get("evidence", ""))
    if any(ev in t for t in textos_norm):
        cita_ok += 1
    else:
        cita_mal += 1
        malas.append(f)
    if f.get("section_sha256") in por_sha:
        sha_ok += 1
    else:
        sha_mal += 1

print("=" * 64)
print("AUDITORÍA INDEPENDIENTE · 280 fichas del harness")
print("=" * 64)
print(f"citas que SÍ están literales en el corpus : {cita_ok}")
print(f"citas que NO he podido encontrar          : {cita_mal}")
print(f"sha256 que casa con una sección real      : {sha_ok}")
print(f"sha256 huérfano                           : {sha_mal}")

if malas:
    print("\nCitas no encontradas (las 3 primeras):")
    for f in malas[:3]:
        print(f"  [{f['book']}] {f['evidence'][:90]}…")

# --- longitudes y forma, contra las manuales
def perfil(lista, etiqueta):
    ev = [len(c.get("evidence", "")) for c in lista]
    an = [len(c.get("answer", "")) for c in lista]
    tp = [len(c.get("topics", []) or []) for c in lista]
    con_pregunta = sum(1 for c in lista if c.get("question"))
    print(f"\n{etiqueta} (n={len(lista)})")
    print(f"  cita   : media {sum(ev)/len(ev):5.0f}  min {min(ev):4d}  max {max(ev):4d}")
    print(f"  respuesta: media {sum(an)/len(an):5.0f}  min {min(an):4d}  max {max(an):4d}")
    print(f"  temas  : media {sum(tp)/len(tp):4.1f}")
    print(f"  con pregunta: {con_pregunta}/{len(lista)}")

perfil(manuales, "FICHAS A MANO (patrón)")
perfil(fichas, "FICHAS DEL HARNESS")

print("\nCobertura por libro:")
mb = Counter(c.get("book", "?") for c in manuales)
hb = Counter(c.get("book", "?") for c in fichas)
cb = Counter(s.get("book", "?") for s in secciones)
print(f"  {'libro':12s} {'corpus':>7s} {'a mano':>7s} {'harness':>8s}")
for libro in sorted(cb, key=lambda x: -cb[x]):
    print(f"  {libro:12s} {cb[libro]:7d} {mb[libro]:7d} {hb[libro]:8d}")

# --- campos del contrato
campos_manual = set(manuales[0].keys())
campos_harness = set(fichas[0].keys())
print(f"\nCampos que pide el contrato y NO trae el harness: "
      f"{sorted(campos_manual - campos_harness) or 'ninguno'}")
print(f"Campos extra del harness: {sorted(campos_harness - campos_manual)}")

# --- duplicados
citas = [normalizar(f.get('evidence', '')) for f in fichas]
dup = sum(v - 1 for v in Counter(citas).values() if v > 1)
print(f"\nCitas repetidas entre fichas: {dup}")
