# GeneradorAnaliticosFinales
Generador de Analíticos finales - Alumnos

## Macros

| Archivo | Qué hace |
| --- | --- |
| `ExtraerDatos` | Lee el PDF del certificado analítico parcial y pega todo en la planilla (hojas `EDITOR`, `Datos` y `Extractor`). |
| `GenerarAnalitico` | Arma el `.odt` final a partir del modelo y actualiza el `Listado`. |
| `ChequearPlan.py` | Compara las materias del alumno con el plan de estudios de la carrera y avisa si le falta alguna. |
| `ImportarPlan.py` | Arma el plan de una carrera: desde la lista que ya tiene la planilla, o desde el PDF del plan. |
| `pruebas_ChequearPlan.py` | Pruebas del chequeo y del importador. Se corre con `python3 pruebas_ChequearPlan.py`, sin LibreOffice. |

Los scripts van juntos en la carpeta de macros de usuario de LibreOffice,
con extensión `.py`:

* Linux: `~/.config/libreoffice/4/user/Scripts/python/`
* Windows: `%APPDATA%\LibreOffice\4\user\Scripts\python\`

## Chequeo contra el plan de estudios

Responde una sola pregunta: **¿a este alumno le falta alguna materia?**

### Cómo se usa

Botón en la hoja (o Herramientas → Macros), asignado a la macro `ChequearPlan`.
Se corre cuando uno quiere, no solo: el momento útil es **antes de generar el
analítico**, con los datos ya cargados y revisados. Ahí el chequeo hace de
última red por si el alumno no estaba recibido.

Al terminar muestra un cartel con el resultado y deja el detalle materia por
materia en una hoja nueva llamada `Chequeo`, encabezada con la fecha y el
alumno.

**No hace falta limpiarla entre alumno y alumno:** cada chequeo borra la hoja y
la escribe de nuevo, así que nunca quedan renglones del anterior. Para dejarla
en blanco al terminar hay dos opciones:

* la macro `LimpiarChequeo` (Herramientas → Macros, o un botón);
* agregar esto al final de tu macro `LIMPIAR`, así se limpia junto con el resto:

```basic
If ThisComponent.Sheets.hasByName("Chequeo") Then
    oHoja = ThisComponent.Sheets.getByName("Chequeo")
    oCur = oHoja.createCursor()
    oCur.gotoEndOfUsedArea(False)
    oHoja.getCellRangeByPosition(0, 0, oCur.RangeAddress.EndColumn, _
        oCur.RangeAddress.EndRow).clearContents(1 + 2 + 4 + 16)
End If
```

Si preferís que la hoja desaparezca del todo, `ThisComponent.Sheets.removeByName("Chequeo")`:
el chequeo siguiente la vuelve a crear.

### Planes ya cargados

* `Planes de estudio/ENFERMERIA.txt` — sacado del PDF oficial (Res. CDFCNyCS
  104/18): 19 materias y 95 hs de actividades electivas.
* `Planes de estudio/EJEMPLO - TECNICATURA EN ENFERMERIA.txt` — inventado, solo
  para mostrar el formato.

### La carpeta de planes

Una carpeta cuyo nombre empiece con `Planes` (sirve `PLANES DE ESTUDIO`), con
**un archivo de texto por carrera**. Se busca al lado del `.ods`, en la carpeta
de arriba y en las de trabajo de siempre.

Los PDF de los planes pueden quedar en la misma carpeta: la macro **no los lee**,
solo mira los `.txt`. Tampoco entra en las subcarpetas, así que una subcarpeta
tipo `bak` sirve de "pendientes" sin molestar.

```
PLANES DE ESTUDIO/
├── Plan-de-estudios-Geologia.pdf          <- el oficial, como respaldo
├── Plan-de-estudios-Geologia.txt          <- este es el que usa la macro
├── Plan-de-estudios-Geologia.crudo.txt    <- texto del PDF, por si hace falta
└── bak/                                   <- los que todavía no revisaste
```

### Cargar un plan nuevo

Hay dos caminos, en `ImportarPlan.py`. **Probá primero el de la planilla**, que
es más confiable.

**A) Desde la planilla** — macro `ImportarPlanDeLaPlanilla`

La planilla ya tiene, en `Datos!AZ`, la lista de materias de la carrera elegida
(la del desplegable de ASIGNATURAS). Elegí la carrera en el cuadro del EDITOR y
corré la macro: escribe el `.txt` en la carpeta de planes, con la línea
`CARRERA:` ya puesta y los nombres escritos **igual que en el analítico**, así
que no queda nada que emparejar.

Si esa carrera no tiene la lista cargada (`Datos!AZ` vacío o con `#¡REF!`), la
macro te lo dice y ahí sí va el PDF.

**B) Desde el PDF del plan** — macro `ImportarPlanPDF`

Elegí uno o varios PDF; deja un `.txt` al lado de cada uno con las materias que
detectó, más un `.crudo.txt` con el texto del PDF tal cual por si hace falta
copiar y pegar.

**En los dos casos, abrí el `.txt` y revisalo una vez:**

1. Que estén todas las materias y ninguna de más (el importador desde PDF deja
   comentados al final los renglones que descartó).
2. `CARRERA:` tiene que decir lo mismo que `Datos!AZ3`.
3. `ELECTIVAS: N` o `ELECTIVAS_HS: N`, según cómo las pida el plan.

Hecho eso, esa carrera queda lista para siempre (salvo que cambie el plan).

**No hace falta renombrar los PDF:** el plan se encuentra por la línea
`CARRERA:` del `.txt`, no por el nombre del archivo. Igual, un nombre
descriptivo ayuda a encontrarlo a ojo.

### Formato del plan

```
CARRERA: ENFERMERIA
TITULO: Enfermero/a (Res. CDFCNyCS 104/18)
ELECTIVAS_HS: 95

[Primer año]
ANATOMIA Y FISIOLOGIA | ANATOMOFISIOLOGIA
ENFERMERIA BASICA
? SEMINARIO DE INGLES
```

* `CARRERA: ...` = con qué nombre se pide este plan; tiene que decir lo mismo
  que `Datos!AZ3`. Se puede repetir (siglas, el nombre viejo de la carrera). Si
  no está, se usa el nombre del archivo.
* `#` al principio del renglón = comentario. También sirve al final de un
  renglón: `FISICA I   # ver correlativas`.
* `[...]` = título de grupo (año). Solo sale en el informe.
* `TITULO: ...` = el nombre que aparece en el cartel.
* `ELECTIVAS: N` = cuántas actividades electivas pide el plan.
* `ELECTIVAS_HS: N` = para los planes que las piden por carga horaria (es el
  caso de Enfermería: 95 hs). Las horas salen de la columna `Hs.` del EDITOR,
  que se completa a mano solo para las electivas. Las desaprobadas o ausentes
  no suman. Si alguna electiva quedó sin horas cargadas, o no se pudo leer la
  columna, el chequeo lo avisa en vez de darlas por faltantes.
* `MATERIA | OTRO NOMBRE` = nombres alternativos, para cuando el analítico la
  escribe distinto que el plan.
* `?` adelante = no obligatoria: si falta, se informa pero no bloquea. (Ojo:
  esto no son las actividades electivas, que van con `ELECTIVAS:`.)

Está todo explicado también en `Planes de estudio/EJEMPLO - TECNICATURA EN ENFERMERIA.txt`.

### Cómo compara

* Las materias del alumno salen de la hoja `Datos` (columna B el nombre,
  columna D la calificación) y, si `Datos` está vacía, de `Extractor`.
* Para comparar los nombres no importan tildes, mayúsculas, guiones ni los
  códigos del tipo `1A - `; `II` cuenta igual que `2`.
* Si el nombre no coincide letra por letra, busca el más parecido: esas
  coincidencias se informan aparte, bajo *coincidencias aproximadas*, para que
  las mires.
* Cuenta como aprobada la nota de 4 para arriba, `Aprobado` y
  `Aprobado por Resolución ...` (equivalencias). `Ausente` y las notas menores
  a 4 quedan como pendientes. Si una materia figura dos veces, vale la aprobada.
* Las actividades electivas se cuentan aparte: por cantidad (`ELECTIVAS:`) o
  sumando las horas de la columna `Hs.` del EDITOR (`ELECTIVAS_HS:`). Si alguna
  quedó con el texto del desplegable (`ACTIVIDAD ELECTIVA: ESCRIBIR SU
  NOMBRE...`), avisa: ese texto sale tal cual en el analítico.
* Una materia que figura varias veces (el aplazo o el ausente y después la
  aprobada) **no** es una materia ajena al plan: los intentos anteriores se
  informan aparte, como `INTENTO ANTERIOR`, debajo de su materia.

### Ajustes

Arriba de todo en `ChequearPlan.py`:

* `NOTA_MINIMA = 4` — de qué nota para arriba cuenta como aprobada.
* `UMBRAL_PARECIDO = 0.86` — cuánto se tienen que parecer dos nombres para
  darlos por la misma materia. Más alto = más estricto.
* `NOMBRE_HOJA_INFORME = "Chequeo"` — la hoja donde va el detalle.
