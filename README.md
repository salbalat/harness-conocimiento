# Harness de conocimiento

Convierte secciones de libros reales en **fichas citables**: pregunta, cita literal del
original, respuesta y localizador. Nació para desatascar el proyecto de yoga, que tenía
502 secciones de libros guardadas y **solo 16 verificadas a mano**.

## La regla que lo sostiene

**La cita se comprueba contra el original POR CÓDIGO, no por un modelo.**

Un modelo propone la ficha; el código verifica que la cita existe de verdad en el texto.
Un modelo puede equivocarse, exagerar o inventar — pero no puede colar una cita que no
está, porque quien decide eso no es él. Esa es toda la idea.

## Cómo funciona

```
sección del libro
   ↓
[1] proponedor (qwen2.5:14b)     → pregunta + cita + respuesta + temas
   ↓
[2] PUERTA (código, sin modelo)  → ¿la cita está literal en el original?  NO → descarte
   ↓
[3] cribador (mistral-small:24b) → ¿la respuesta se sostiene SOLO con esa cita?
   ↓
[4] ficha con sha256 de la sección
   ↓
 sí → fichas/     dudosa → cola/ (revisión humana)
```

El proponedor y el cribador son **modelos distintos a propósito**. Si fueran el mismo,
se daría la razón a sí mismo.

## Uso

```bash
cd ~/harness-conocimiento
python3 harness.py --limite 10              # prueba corta
python3 harness.py --solo-libro hatha       # un libro
python3 harness.py                          # todo el corpus
```

Resultados en `fichas/`, dudosas en `cola/`, traza completa en `logs/`.

## Decisiones tomadas (y por qué)

**La comparación de citas ignora los espacios.** Los PDF del corpus están mal extraídos:
hay títulos con las letras separadas (`I a m  f o r e v e r`), palabras partidas por el
guionado (`le arned`) y saltos de línea dentro de las frases. El modelo lee eso y copia
la cita bien escrita, que es lo correcto; comparando con espacios se rechazaban citas
verdaderas. Sin espacios sigue siendo prueba sólida: que 40+ caracteres coincidan por
azar es imposible. **Antes de este arreglo: 0 fichas aprobadas de 12 en Hart. Después: 5.**

**Las secciones largas se trocean** (5.000 caracteres, 400 de solape). El corpus es muy
desigual: Frankl trae secciones de ~1.100 caracteres, pero Hatha Yoga Pradípika son 4
CAPÍTULOS de ~45.000 y `safety` una pieza de 66.886. Sin trocear se sacaba una sola ficha
por capítulo y se tiraba el 87% de esos libros.

**El `section_sha256` se calcula sobre la sección completa**, no sobre el fragmento, para
no romper el mecanismo de yoga que descarta una ficha si el texto original cambia.

## Contrato de salida

Mismo formato que `verified_cards.json` del proyecto de yoga, para que las fichas se
puedan incorporar directamente:

```
id, book, title, book_title, book_author, section, locator,
evidence,          # cita literal, verificada por código
answer, question, topics[],
reviewed,          # false: ninguna ficha del harness se marca revisada por Salvador
review_date, section_sha256,
harness{ proponedor, cribador, veredicto, motivo }
```

`reviewed` siempre sale **false**: el harness no puede firmar por Salvador. Lo que hace es
quitarle de encima el trabajo de lectura, no la autoridad.

## Derechos

Los libros tienen copyright (Frankl, Hart, Sogyal Rimpoché; el Siddhartha en inglés es de
Gutenberg). **El texto íntegro se queda aquí, en local, como material de verificación.**
Hacia fuera solo sale cita breve + autor + obra + página + redacción propia, que es lo que
el proyecto de yoga ya hacía.

## Límites conocidos

- **El corpus está sesgado**: 236 secciones de Frankl y 164 de Hart son el 80% del total.
  Yoga postural tiene muy poco. El harness no arregla eso: si quieres un asesor de yoga,
  falta corpus de yoga.
- **La calidad depende del PDF de origen.** Donde la extracción es mala, se pierden fichas.
- Prólogos, índices y notas de edición se descartan (el modelo los marca «no útil»),
  y está bien: no son conocimiento.

## Estado

Ver `ESTADO.md`.
