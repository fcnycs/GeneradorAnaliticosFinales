# GeneradorAnaliticosFinales
Generador de Analíticos finales - Alumnos

## Macros

| Archivo | Qué hace |
| --- | --- |
| `ExtraerDatos` | Lee el PDF del certificado analítico parcial y pega todo en la planilla (hojas `EDITOR`, `Datos` y `Extractor`). |
| `GenerarAnalitico` | Arma el `.odt` final a partir del modelo y actualiza el `Listado`. |
| `ChequearPlan.py` | Compara las materias del alumno con el plan de estudios de la carrera y avisa si le falta alguna. |
| `pruebas_ChequearPlan.py` | Pruebas de la lógica del chequeo. Se corre con `python3 pruebas_ChequearPlan.py`, sin LibreOffice. |

Los tres scripts van juntos en la carpeta de macros de usuario de LibreOffice,
con extensión `.py`:

* Linux: `~/.config/libreoffice/4/user/Scripts/python/`
* Windows: `%APPDATA%\LibreOffice\4\user\Scripts\python\`

## Chequeo contra el plan de estudios

Responde una sola pregunta: **¿a este alumno le falta alguna materia?**

### Cómo se usa

* **Solo:** botón en la hoja, asignado a la macro `ChequearPlan`.
* **Automático:** `ExtraerDatos` lo llama al terminar la extracción. Si todavía
  no está cargado el plan de esa carrera, no dice nada y sigue de largo.

Al terminar muestra un cartel con el resultado y deja el detalle materia por
materia en una hoja nueva llamada `Chequeo`.

### La carpeta de planes

Una carpeta llamada `Planes de estudio` con **un archivo de texto por carrera**.
Se busca al lado del `.ods` (y en la carpeta de arriba y en las de trabajo de
siempre). El archivo se elige por su nombre, que tiene que parecerse al de la
carrera que figura en `Datos!AZ3`; si no lo encuentra, abre el diálogo para
elegirlo a mano.

### Formato del plan

```
TITULO: Tecnicatura Superior en Enfermería (Res. 000/00)
ELECTIVAS: 2

[Primer año]
ANATOMIA Y FISIOLOGIA | ANATOMOFISIOLOGIA
ENFERMERIA BASICA
? SEMINARIO DE INGLES
```

* `#` al principio del renglón = comentario.
* `[...]` = título de grupo (año). Solo sale en el informe.
* `ELECTIVAS: N` = cuántas actividades electivas pide el plan.
* `MATERIA | OTRO NOMBRE` = nombres alternativos, para cuando el analítico la
  escribe distinto que el plan.
* `?` adelante = optativa: si falta, se informa pero no bloquea.

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

### Ajustes

Arriba de todo en `ChequearPlan.py`:

* `NOTA_MINIMA = 4` — de qué nota para arriba cuenta como aprobada.
* `UMBRAL_PARECIDO = 0.86` — cuánto se tienen que parecer dos nombres para
  darlos por la misma materia. Más alto = más estricto.
* `NOMBRE_HOJA_INFORME = "Chequeo"` — la hoja donde va el detalle.
