# ESTADO · Harness de conocimiento — 20-09-2026

Estado real. Manda sobre cualquier suposición. Ver `README.md` para el camino.

## Dónde vive

**En el servidor MEISSON**: `/home/perrix/harness-conocimiento/`
(decisión del 20-09-2026, norma nº1 de Salvador: se trabaja en el servidor).
El Mac solo se usa para mirar resultados.

```
harness.py        el harness
auditar.py        auditoría independiente de las fichas (no se fía del harness)
simular_jasper.py simula las puertas de Jasper sobre las fichas, sin tocar Jasper
corpus/           sections.json (502 secciones) + verified_cards.json (16 fichas patrón)
fichas/           fichas aprobadas, por pasada con marca de tiempo
cola/             dudosas, para revisión de Salvador
logs/             traza de cada pasada
```

## Modelos (comprobado el 20-09-2026)

Ollama corre en el **Windows anfitrión**, y desde WSL se llega por la IP del anfitrión
(la que sale en `/etc/resolv.conf`), NO por la IP de la LAN, que no responde.
Se configura con la variable `OLLAMA_URL`. El
`ollama_proxy.py` de `~/herramientas/` ya se autodetecta el gateway.

Hay **19 modelos**. En uso:
- proponedor: `qwen2.5:14b`
- cribador: `mistral-small:24b` (distinto a propósito)

Alternativas si hiciera falta más músculo: `qwen2.5:72b-instruct-q2_K` (29,8 GB),
`qwen3.5:35b-a3b`, `deepseek-r1:14b`, `gemma4:12b`.

## Lo que se hizo el 20-09-2026

1. Proyecto creado en el servidor, corpus subido desde el Mac.
2. `harness.py` escrito y probado.
3. **Dos fallos encontrados y corregidos con datos, no a ojo:**
   - *Citas verdaderas rechazadas.* Vipassana daba **0 aprobadas de 12**. Causa: el PDF
     está mal extraído (`I a m  f o r e v e r`, `le arned`, saltos de línea en medio de
     frases); el modelo copiaba la cita bien escrita y la comparación literal la tumbaba.
     Arreglo: comparar ignorando espacios. **Resultado: 5 aprobadas de 12.**
   - *Libros desaprovechados.* Hatha son 4 capítulos de ~45.000 caracteres y solo se leían
     los primeros 6.000: se tiraba el 87%. Arreglo: trocear a 5.000 con 400 de solape.
     **502 secciones → 592 fragmentos.**
4. **Pasada completa terminada: 592/592 en 92 minutos.**
   `aprobadas: 280 · a revisar: 206 · descartadas: 106`
   Fichero: `fichas/fichas-20260920-091748.json`

## Auditoría independiente de las 280 (`auditar.py`)

No se fía del harness: vuelve a comprobar cada ficha contra el corpus.

| comprobación | resultado |
|---|---|
| citas que SÍ están literales en el corpus | **280 / 280** |
| sha256 que casa con una sección real | **280 / 280** |
| campos del contrato que faltan | ninguno |
| citas repetidas entre fichas | 8 (por el solape del troceo) |

Contra las 16 hechas a mano: la cita del harness mide **186 caracteres de media**
frente a **31** de las manuales (una manual tiene 10 caracteres, que no prueba nada).
La respuesta mide 182 de media en ambas. Donde a mano había 1 ficha de Frankl, hay 94.

**Calidad, lo que los números no dicen:** 42 de las 280 salen de paratexto editorial
(prólogos, contraportadas). 39 de ellas son de `joy` y `tibetan`, y **no es culpa del
harness**: el propio corpus dice `coverage: "solo muestra editorial, no libro completo"`.
De esos dos libros no hay cuerpo que leer. Hay alguna ficha que es un *blurb* de
contraportada («no he encontrado ningún libro más completo»): eso no es conocimiento.

## LO IMPORTANTE: Jasper hoy rechazaría las 280 (`simular_jasper.py`)

Medido simulando `verified_answers.py:14-26` sobre las fichas, sin tocar Jasper:

| puerta de Jasper | tumba | qué es |
|---|---|---|
| `reviewed is not True` (línea 20) | **280** | decisión de Salvador, no un fallo |
| `locator` no casa (línea 19) | 53 | el harness escribe «· fragmento N» en `section` |
| cita con espacios **colapsados** (línea 21) | 50 | **Jasper tiene el bug del PDF que el harness ya arregló** |
| sha256 (línea 24) | **0** | el diseño de guardar el sha de la sección completa aguantó |

**Si se meten tal cual: 0 fichas utilizables.** Jasper seguiría igual que hoy.
Arreglando las dos puertas técnicas (`locator` y espacios): **177 fichas** listas,
a falta de decidir el `reviewed`.

## HECHO: las fichas están en Jasper y funciona (20-09-2026)

Salvador decidió: **tercer estado etiquetado** (ni firmar por él, ni dejarlo sin usar)
y dio permiso para tocar Jasper con copia previa.

- `preparar_para_jasper.py` deja **272 fichas** listas (de 280: caen 8 duplicadas del
  solape). Arregla el `section` y **normaliza los topics con la `words()` de Jasper**,
  copiada literal: el modelo escribía `haṭha yoga` y `candidates()` exige intersección
  literal, así que la ficha buena existía pero no se encontraba nunca.
- En Jasper (`verified_answers.py`, copia en `.bak-before-harness-2026-09-20-1103`):
  carga `harness_cards.json` aparte, acepta `verified_by == 'harness'` marcándolo como
  **«(verificación automática)»**, y se le arregló el mismo bug de los espacios que
  tenía el harness (tumbaba 50 citas verdaderas).
- **`verified_cards.json` no se ha tocado**: las 16 fichas de Salvador siguen igual y
  se comprobó que ninguna se pierde. Borrando `harness_cards.json`, Jasper vuelve atrás.

**Prueba de éxito** hecha por HTTP con el modelo real: «¿Cómo debe ser el lugar para
practicar hatha yoga?» antes daba *«No tengo contenido verificado suficiente»*; ahora
contesta con la cita literal del Capítulo 1 y su fuente.

## La cola rescatada: 183 de 206 (88%) — `rescatar_cola.py`

Las fichas de la cola **tenían la cita ya verificada por código**; lo que el cribador
rechazaba era la respuesta: 172 de 206 por «añade datos que no están en la cita». El
modelo los añadía porque veía el PASAJE ENTERO y se traía contexto de fuera.

**El arreglo: en el rescate el modelo ve SOLO LA CITA.** Si no tiene el pasaje delante,
no puede añadir lo que no está. Después se vuelve a cribar con el modelo severo.
Resultado: **183 rescatadas de 206 en 35 minutos.**

Ojo con las muestras pequeñas: las 8 primeras daban 25%, pero eran todas de `hatha`,
el libro más difícil (listas de alimentos, detalles de posturas). El global fue 88%.

## Paratexto apartado: 12 fichas — `quitar_paratexto.py`

Las 34 candidatas se leyeron **una a una**; la heurística automática no valía. La
«muestra editorial» de `tibetan` incluye los primeros capítulos de verdad (la muerte de
Lama Tseten, la pereza occidental, la impermanencia): eso es el libro y se queda.

Se apartaron 12: el *blurb* de contraportada, la dedicatoria, cuatro trozos de prólogo
sobre la buena acogida del libro, el prólogo de Allport elogiando a Frankl, y tres
anécdotas de `joy` (una explica por qué el Dalái Lama no va al aeropuerto).
Van a `descartadas_paratexto.json` **con el motivo escrito**, no se borran.

## Estado final: Jasper pasa de 16 fichas a 458

**442 fichas del harness + las 16 de Salvador.** Verificadas de forma independiente:
442/442 con cita literal en el corpus y 442/442 con sha256 correcto.

## Corpus de yoga incorporado (20-09-2026, tarde) — `incorporar_fuentes.py`

El corpus estaba sesgado (Frankl + Hart = 80%) y de yoga postural solo había 4 capítulos.
Se añadieron **cinco fuentes de dominio público**, en `corpus/fuentes/`:

| fuente | texto útil | aporta |
|---|---|---|
| Gheranda + Siva Samhita (Vasu 1915) | 430 KB | 21 asanas con ejecución paso a paso |
| Yoga-Mimansa (Kuvalayananda 1928) | 473 KB | asanas y pranayama con fisiología |
| Hatha Yoga Pradipika completo (Sinh 1915) | 84 KB | el libro entero |
| Science of Breath (Gutenberg #13402) | 125 KB | pranayama, sin OCR |
| NCCIH del NIH (yoga + meditación) | 67 KB | evidencia clínica y seguridad |

**Corpus: 502 → 768 secciones.** Cada fichero se verificó contando términos antes de
incorporarlo (`asana=140, mudra=128` en el Gheranda), no por lo que dijera su ficha.

**El limpiador hay que hacerlo POR LÍNEA, no por párrafo.** La primera versión filtraba
por párrafo y se comía el 73% del Hatha Pradipika: los escaneos no traen párrafos, son
líneas sueltas de OCR (1.402 en ese libro, 1.315 de menos de 200 caracteres), y entre lo
que tiraba había texto bueno. Por línea: 78% conservado en Hatha, 91% en Yoga-Mimansa.

Pasadas sobre lo nuevo: **114 fichas aprobadas** + 59 rescatadas de sus colas (83%).

## Estado: Jasper tiene 632 fichas (16 de Salvador + 616 del harness)

**Yoga postural y respiratorio: de 31 fichas a 206.** Probado por HTTP con el modelo:
«¿Cómo se hace la postura del loto?» devuelve el Padmâsana paso a paso citando el
Hatha Yoga Pradípika. En «¿el yoga ayuda con el dolor lumbar?» mezcla NCCIH con una
ficha revisada por Salvador que matiza que no se puede prometer curación: el tercer
estado funciona.

## Trampa que costó tiempo: `pgrep -f` se encuentra a sí mismo

Encadenar pasadas con `while pgrep -f "harness.py --solo-libro"; do sleep 30; done`
**no funciona**: esa cadena está en la propia línea de comandos del bucle, así que
pgrep siempre se encuentra y espera para siempre. Pasó dos veces. Para encadenar,
esperar por el contenido del log, no por pgrep.

## Pendiente
- Jasper sigue **sin git**: convendría ponerlo, ahora que se le han tocado ficheros.
- El corpus de yoga postural sigue siendo mínimo: si se quiere un asesor de yoga de
  verdad, **falta corpus de yoga**, y eso el harness no lo puede inventar.

## Avisos

- **El corpus está sesgado**: 236 secciones de Frankl + 164 de Hart = 80% del total.
  Yoga postural tiene 4 secciones de Hatha y poco más. El harness multiplica lo que hay;
  no inventa lo que falta. **Si lo que se quiere es un asesor de yoga, falta corpus de yoga.**
- `joy` y `tibetan` son **solo muestra editorial**, no el libro. Lo dice su `coverage`.
- El proyecto de yoga sigue **solo en el Mac y sin git**
  (`~/Projects/jasper-yoga-preview-20260916`). Al devolverle las fichas, hacer copia antes.
- Derechos: texto íntegro solo local; hacia fuera, cita breve con fuente.
