# GeneradorAnaliticosFinales
Generador de Analíticos finales - Alumnos

## Macros

| Archivo | Qué hace |
| --- | --- |
| `ExtraerDatos` | Lee el PDF del certificado analítico parcial y pega todo en la planilla (hojas `EDITOR`, `Datos` y `Extractor`). |
| `GenerarAnalitico` | Arma el `.odt` final a partir del modelo y actualiza el `Listado`. |
| `ChequearPlan.py` | Compara las materias del alumno con el plan de estudios de la carrera y avisa si le falta alguna. |
| `ImportarPlanPDF.py` | Pasa un plan de estudios en PDF a un borrador de texto, para no cargarlo a mano. |
| `pruebas_ChequearPlan.py` | Pruebas del chequeo y del importador. Se corre con `python3 pruebas_ChequearPlan.py`, sin LibreOffice. |

Los scripts van juntos en la carpeta de macros de usuario de LibreOffice,
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

### Cargar un plan nuevo (desde el PDF)

1. **Herramientas → Macros → Ejecutar macro → Mis macros → ImportarPlanPDF**, y
   elegí el o los PDF (se pueden marcar varios de una).
2. Deja un `.txt` al lado de cada PDF, con las materias que detectó.
3. **Abrilo y revisalo una vez.** Es un borrador: puede colarse un renglón de
   más o faltar alguno. Al final del archivo quedan comentados los renglones
   que descartó, por si alguno era una materia.
4. Sobre todo, dejá la línea `CARRERA:` diciendo lo mismo que `Datos!AZ3`, y
   completá `ELECTIVAS:` si el plan pide actividades electivas.

Hecho eso, esa carrera queda lista para siempre (salvo que cambie el plan).

**No hace falta renombrar los PDF:** el plan se encuentra por la línea
`CARRERA:` del `.txt`, no por el nombre del archivo. Igual, un nombre
descriptivo ayuda a encontrarlo a ojo.

### Formato del plan

```
CARRERA: Tecnicatura Superior en Enfermería
CARRERA: TSE
TITULO: Tecnicatura Superior en Enfermería (Res. 000/00)
ELECTIVAS: 2

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
