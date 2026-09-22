#!/usr/bin/env python3
"""Aparta las fichas que no son conocimiento, sino paratexto editorial.

Las 34 candidatas (muestra editorial o páginas bajas) se leyeron UNA A UNA. La
heurística automática no vale: la «muestra editorial» de `tibetan` incluye los
primeros capítulos de verdad del libro (la muerte de Samten, la pereza occidental,
la impermanencia), que SÍ son conocimiento. Solo se aparta lo que habla *del libro*
en vez de decir algo: contraportadas, dedicatorias, prólogos sobre su recepción y
anécdotas logísticas del narrador.

No borra nada: mueve a `descartadas_paratexto.json` con el motivo, y regenera
`harness_cards.json` sin ellas. Reversible.
"""
import json
from pathlib import Path

RAIZ = Path("/home/perrix/harness-conocimiento")

FUERA = {
    "tibetan_0241": "blurb de contraportada: elogio del propio libro, no dice nada del tema",
    "tibetan_0245": "dedicatoria del autor a sus maestros",
    "tibetan_0251": "prólogo sobre la buena acogida que tuvo el libro",
    "tibetan_0252": "anécdota sobre el impacto del libro en una lectora",
    "tibetan_0253": "cita de la misión de una fundación, no del contenido",
    "tibetan_0254": "prólogo valorando la aportación del propio libro",
    "meaning_0344": "prólogo de Allport elogiando la honestidad de Frankl",
    "tibetan_0255": "prologo: habla de lo fertil que fue escribir el libro",
    "joy_0211": "declaración de intenciones del libro ('esperamos que este libro sea...')",
    "joy_0213": "preámbulo retórico, no responde a ninguna pregunta",
    "joy_0221": "anécdota personal del coautor (le hormiguea la cabeza)",
    "joy_0237": "anécdota logística: por qué el Dalái Lama no va al aeropuerto",
}

fichas = json.loads((RAIZ / "harness_cards.json").read_text(encoding="utf-8"))

# ACUMULA: el preparador lee este fichero para no readmitir lo ya descartado, así que
# sobrescribirlo con solo la tanda nueva haría volver a las anteriores en la siguiente
# regeneración. Se conservan todas.
destino = RAIZ / "descartadas_paratexto.json"
previas = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else []
apartadas = {f["id"]: f for f in previas}

quedan = []
for f in fichas:
    motivo = FUERA.get(f.get("id"))
    if motivo:
        apartadas[f["id"]] = {**f, "motivo_descarte": motivo}
    else:
        quedan.append(f)
apartadas = list(apartadas.values())

destino.write_text(json.dumps(apartadas, ensure_ascii=False, indent=2), encoding="utf-8")
(RAIZ / "harness_cards.json").write_text(
    json.dumps(quedan, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"entraban : {len(fichas)}")
print(f"apartadas: {len(apartadas)}  -> descartadas_paratexto.json")
print(f"quedan   : {len(quedan)}")
no_encontradas = set(FUERA) - {f['id'] for f in apartadas}
if no_encontradas:
    print(f"AVISO: no estaban en el fichero: {sorted(no_encontradas)}")
