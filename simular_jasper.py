#!/usr/bin/env python3
"""Simula EXACTAMENTE las puertas de Jasper (verified_answers.py:14-26)
sobre las 280 fichas del harness, para saber cuántas sobrevivirían de verdad.

No toca nada. Solo cuenta.
"""
import hashlib, json, re
from pathlib import Path

RAIZ = Path("/home/perrix/harness-conocimiento")


def normalize(text):                       # copiado literal de Jasper
    return re.sub(r"\s+", " ", text).strip()


content = json.loads((RAIZ / "corpus" / "sections.json").read_text(encoding="utf-8"))
fichas = json.loads((RAIZ / "fichas" / "fichas-20260920-091748.json").read_text(encoding="utf-8"))

cae_reviewed = cae_locator = cae_evidence = cae_sha = pasa = 0
ejemplo_locator = ejemplo_evidence = None

for entry in fichas:
    # puerta 1: reviewed
    if entry.get("reviewed") is not True:
        cae_reviewed += 1
        # seguimos evaluando para saber si, aparte del reviewed, pasaría
    # puerta 2: encontrar la sección por book + locator exacto
    section = next((s for s in content
                    if s["book"] == entry["book"] and s["locator"] == entry["section"]), None)
    if section is None:
        cae_locator += 1
        if ejemplo_locator is None:
            ejemplo_locator = entry["section"]
        continue
    # puerta 3: cita literal con espacios COLAPSADOS (no eliminados)
    if normalize(entry["evidence"]) not in normalize(section["text"]):
        cae_evidence += 1
        if ejemplo_evidence is None:
            ejemplo_evidence = entry["evidence"][:80]
        continue
    # puerta 4: sha256
    if entry.get("section_sha256") != hashlib.sha256(section["text"].encode()).hexdigest():
        cae_sha += 1
        continue
    pasa += 1

print("=" * 64)
print("SIMULACIÓN DE LAS PUERTAS DE JASPER · 280 fichas del harness")
print("=" * 64)
print(f"puerta 1  reviewed is not True          -> tumba {cae_reviewed:3d}  (TODAS)")
print(f"puerta 2  locator no casa con sections  -> tumba {cae_locator:3d}")
print(f"puerta 3  cita con espacios colapsados  -> tumba {cae_evidence:3d}")
print(f"puerta 4  sha256 no casa                -> tumba {cae_sha:3d}")
print(f"{'':10s}SOBREVIVEN (ignorando reviewed)  -> {pasa:3d}")
print()
if ejemplo_locator:
    print(f"ejemplo de locator que no casa : «{ejemplo_locator}»")
if ejemplo_evidence:
    print(f"ejemplo de cita que Jasper tumba: «{ejemplo_evidence}…»")
print()
print(f"Resultado real si se meten tal cual: {0 if cae_reviewed == len(fichas) else pasa} fichas utilizables.")
