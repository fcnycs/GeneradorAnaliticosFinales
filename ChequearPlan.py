# -*- coding: utf-8 -*-
"""
Chequeo de materias contra el plan de estudios
==============================================
Compara las materias que figuran en el analítico con el plan de estudios de la
carrera y avisa si al alumno le falta alguna.

De dónde saca las materias del alumno:
  1) la hoja "Datos" (A11 en adelante), que es la tabla final del analítico;
  2) si "Datos" todavía está vacía, la hoja "Extractor" (lo recién sacado del PDF).

De dónde saca el plan:
  de una carpeta "Planes de estudio" con un archivo de texto por carrera
  (ver el archivo de ejemplo). La carpeta se busca al lado del .ods y en las
  carpetas de trabajo de siempre.

Se puede usar de dos formas:
  1) Desde LibreOffice (botón en el .ods)  ->  ChequearPlan()
  2) Desde la terminal, para probar        ->  python3 ChequearPlan.py plan.txt planilla.ods
"""

import os
import re
import sys
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------

# De esta nota para arriba, la materia cuenta como aprobada.
NOTA_MINIMA = 4

# Qué tan parecidos tienen que ser dos nombres para darlos por la misma materia
# cuando no coinciden letra por letra (0 a 1). Esas coincidencias siempre se
# informan aparte, para que las mires.
UMBRAL_PARECIDO = 0.86

# Hoja donde se escribe el detalle del chequeo (se crea si no existe).
NOMBRE_HOJA_INFORME = "Chequeo"

# Carpetas donde buscar la carpeta de planes, además de la del .ods.
CARPETAS_TRABAJO = [
    r"D:\Documentos Personales\ALUMNOS\Analitico p-titulo",
    "/home/cristian/Documentos/ALUMNOS/Analitico p-titulo",
]

# Una carpeta sirve como carpeta de planes si su nombre empieza así.
PREFIJO_CARPETA_PLANES = "planes"

EXTENSIONES_PLAN = (".txt", ".csv", ".plan")

# Dónde están los datos dentro de la planilla
HOJA_DATOS = "Datos"
COL_NOMBRE_DATOS = 1          # Datos!B = actividad
COL_NOTA_DATOS = 3            # Datos!D = calificación
PRIMERA_FILA_DATOS = 11       # Datos!A11
ULTIMA_FILA_DATOS = 330

HOJA_EXTRACTOR = "Extractor"
COL_NOMBRE_EXTRACTOR = 0      # Extractor!A = actividad
COL_NOTA_EXTRACTOR = 2        # Extractor!C = nota

# Las horas de las actividades electivas están en la hoja EDITOR, que es la
# única que las tiene (la tabla de "Datos" no arrastra la columna Hs.).
HOJA_EDITOR = "EDITOR"
FILA_ENCABEZADO_EDITOR = 16   # EDITOR!17: "ASIGNATURAS | Hs. | FECHA | ..."
PRIMERA_FILA_EDITOR = 17      # EDITOR!18
COL_ASIGNATURA_EDITOR = 4     # EDITOR!E
COL_HS_EDITOR = 5             # EDITOR!F (igual se intenta detectar sola)
PREFIJOS_HS = ("HS", "HORAS", "CARGA")
PREFIJOS_NOTA = ("CALIFICACION", "NOTA")

CELDA_CARRERA = (HOJA_DATOS, "AZ3")
CELDA_GENERO = (HOJA_DATOS, "V4")      # "el Sr. " / "la Srta. "
CELDA_APELLIDO = ("EDITOR", "R4")
CELDA_NOMBRES = ("EDITOR", "S4")


# ---------------------------------------------------------------------------
# NORMALIZACIÓN DE NOMBRES
# ---------------------------------------------------------------------------

# Código de actividad al principio del nombre: "1A - PARASITOLOGIA",
# "MED-2 - FARMACOLOGIA". Se exige que tenga algún número para no comerse
# nombres como "ETICA - DEONTOLOGIA".
_CODIGO_RE = re.compile(r'^(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)*\s*-\s*')

_ROMANOS = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5",
            "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}


def sin_tildes(texto):
    """Saca tildes y diéresis. La Ñ queda como N, que para comparar viene bien."""
    descompuesto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar(texto):
    """Deja el nombre de una materia listo para comparar.

    'MED-1 - Anatomía y Fisiología II' -> 'ANATOMIA Y FISIOLOGIA 2'
    """
    t = sin_tildes(texto or "").upper()
    t = _CODIGO_RE.sub("", t)
    t = re.sub(r'[^A-Z0-9 ]+', ' ', t)
    palabras = [_ROMANOS.get(p, p) for p in t.split()]
    return " ".join(palabras)


def parecido(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _ref_a_columna_fila(ref):
    """'V4' -> (21, 3): columna y fila, contando desde 0."""
    m = re.match(r'([A-Za-z]+)(\d+)', ref or "")
    if not m:
        return 0, 0
    columna = 0
    for letra in m.group(1).upper():
        columna = columna * 26 + (ord(letra) - 64)
    return columna - 1, int(m.group(2)) - 1


# ---------------------------------------------------------------------------
# LECTURA DEL PLAN DE ESTUDIOS
# ---------------------------------------------------------------------------

class MateriaPlan(object):
    """Una materia del plan, con sus nombres alternativos."""

    def __init__(self, nombre, alias=None, grupo="", obligatoria=True, orden=0):
        self.nombre = nombre
        self.orden = orden
        self.alias = alias or []
        self.grupo = grupo
        self.obligatoria = obligatoria
        self.claves = [normalizar(n) for n in [nombre] + self.alias if normalizar(n)]

    def __repr__(self):
        return "MateriaPlan(%r)" % self.nombre


_DIRECTIVA_RE = re.compile(
    r'^(CARRERA|TITULO|T[ÍI]TULO|ELECTIVAS|ELECTIVAS[ _]HS|HORAS[ _]ELECTIVAS)'
    r'\s*:\s*(.*)$', re.IGNORECASE)

# Comentario al final del renglón: "FISICA I   # ver correlativas"
_COMENTARIO_AL_FINAL_RE = re.compile(r'\s+#.*$')


def _leer_texto(ruta):
    """Lee un archivo de texto probando las codificaciones de siempre."""
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(ruta, "r", encoding=codificacion) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise IOError("No se pudo leer el archivo: %s" % ruta)


def leer_plan(ruta):
    """Lee un archivo de plan de estudios y devuelve sus materias.

    Formato (texto plano, un archivo por carrera):

        # lo que empieza con # es un comentario
        CARRERA: Tecnicatura Superior en Enfermería
        TITULO: Tecnicatura Superior en Enfermería (Res. 123/15)
        ELECTIVAS: 2            <- cuántas actividades electivas pide
        ELECTIVAS_HS: 95        <- o cuántas horas, si el plan las pide así

        [Primer año]
        ANATOMIA Y FISIOLOGIA | ANATOMOFISIOLOGIA
        ENFERMERIA BASICA
        ? SEMINARIO DE INGLES        <- el "?" adelante = no es obligatoria

    Lo que va después de "|" son nombres alternativos: sirve para cuando el
    analítico escribe la materia distinto que el plan.

    "CARRERA:" es con lo que la macro encuentra este archivo: tiene que decir
    lo mismo que Datos!AZ3. Se puede repetir para poner otras formas de
    nombrarla. Si no está, se usa el nombre del archivo.
    """
    texto = _leer_texto(ruta)

    plan = {"ruta": ruta, "titulo": "", "electivas": 0, "electivas_hs": 0,
            "carreras": [], "materias": []}
    grupo = ""
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue

        if linea.startswith("[") and linea.endswith("]"):
            grupo = linea[1:-1].strip()
            continue

        directiva = _DIRECTIVA_RE.match(linea)
        if directiva:
            clave = sin_tildes(directiva.group(1)).upper()
            valor = directiva.group(2).strip()
            if clave == "CARRERA":
                if valor:
                    plan["carreras"].append(valor)
            elif clave == "TITULO":
                plan["titulo"] = valor
            else:
                numeros = re.search(r'\d+', valor)
                cantidad = int(numeros.group()) if numeros else 0
                if clave == "ELECTIVAS":
                    plan["electivas"] = cantidad
                else:                      # ELECTIVAS_HS / HORAS_ELECTIVAS
                    plan["electivas_hs"] = cantidad
            continue

        linea = _COMENTARIO_AL_FINAL_RE.sub("", linea).strip()
        if not linea:
            continue

        obligatoria = True
        if linea.startswith("?"):
            obligatoria = False
            linea = linea[1:].strip()

        partes = [p.strip() for p in linea.split("|")]
        nombre = partes[0]
        if not nombre:
            continue
        plan["materias"].append(
            MateriaPlan(nombre, [p for p in partes[1:] if p], grupo, obligatoria,
                        orden=len(plan["materias"])))

    if not plan["titulo"]:
        plan["titulo"] = plan["carreras"][0] if plan["carreras"] else \
            os.path.splitext(os.path.basename(ruta))[0]
    return plan


def buscar_carpetas_de_planes(carpeta_ods=None):
    """Devuelve las carpetas de planes que existan, sin repetir."""
    bases = []
    if carpeta_ods:
        bases += [carpeta_ods, os.path.dirname(carpeta_ods)]
    bases += CARPETAS_TRABAJO

    encontradas, vistas = [], set()
    for base in bases:
        if not base or not os.path.isdir(base):
            continue
        try:
            nombres = os.listdir(base)
        except OSError:
            continue
        for nombre in nombres:
            ruta = os.path.join(base, nombre)
            if not os.path.isdir(ruta):
                continue
            if not sin_tildes(nombre).lower().startswith(PREFIJO_CARPETA_PLANES):
                continue
            if ruta not in vistas:
                vistas.add(ruta)
                encontradas.append(ruta)
    return encontradas


def archivos_de_plan(carpetas):
    archivos = []
    for carpeta in carpetas:
        try:
            nombres = sorted(os.listdir(carpeta))
        except OSError:
            continue
        for nombre in nombres:
            if nombre.lower().endswith(EXTENSIONES_PLAN):
                archivos.append(os.path.join(carpeta, nombre))
    return archivos


def claves_del_plan(ruta):
    """Con qué nombres se puede pedir este plan.

    Son las líneas "CARRERA:" del archivo (puede haber varias) y, además, el
    nombre del archivo. Así no hace falta renombrar nada: alcanza con poner
    adentro del plan la carrera tal como figura en Datos!AZ3.
    """
    claves = []
    try:
        for linea in _leer_texto(ruta).splitlines()[:80]:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            directiva = _DIRECTIVA_RE.match(linea)
            if directiva and sin_tildes(directiva.group(1)).upper() == "CARRERA":
                claves.append(normalizar(directiva.group(2)))
    except (IOError, OSError):
        pass
    claves.append(normalizar(os.path.splitext(os.path.basename(ruta))[0]))
    return [c for c in claves if c]


def buscar_pdf_de_carrera(carrera, carpetas):
    """Busca el PDF oficial del plan de esa carrera, por el nombre del archivo.

    La macro no lee los PDF: esto es solo para poder avisar "está el PDF pero
    todavía no lo importaste".
    """
    clave_carrera = normalizar(carrera)
    if not clave_carrera:
        return None
    mejor, mejor_ratio = None, 0
    for carpeta in carpetas:
        try:
            nombres = sorted(os.listdir(carpeta))
        except OSError:
            continue
        for nombre in nombres:
            if not nombre.lower().endswith(".pdf"):
                continue
            clave = normalizar(os.path.splitext(nombre)[0])
            if not clave:
                continue
            if len(clave) >= 6 and (clave in clave_carrera or clave_carrera in clave):
                ratio = 0.95
            else:
                ratio = parecido(clave, clave_carrera)
            if ratio > mejor_ratio:
                mejor, mejor_ratio = os.path.join(carpeta, nombre), ratio
    return mejor if mejor_ratio >= 0.8 else None


def buscar_plan_de_carrera(carrera, carpetas):
    """Elige el archivo de plan que corresponde a la carrera.

    Devuelve (ruta, exactitud) o (None, 0). La exactitud es 1 cuando el plan
    dice exactamente esa carrera y menos cuando es un parecido.
    """
    clave_carrera = normalizar(carrera)
    if not clave_carrera:
        return None, 0

    mejor, mejor_ratio = None, 0
    for ruta in archivos_de_plan(carpetas):
        for clave in claves_del_plan(ruta):
            if clave == clave_carrera:
                return ruta, 1.0
            # Uno contenido en el otro ("QUIMICA" dentro de "LICENCIATURA EN
            # QUIMICA"). Se piden 6 letras para que una sigla corta no pegue
            # de casualidad.
            if len(clave) >= 6 and (clave in clave_carrera or clave_carrera in clave):
                ratio = 0.95
            else:
                ratio = parecido(clave, clave_carrera)
            if ratio > mejor_ratio:
                mejor, mejor_ratio = ruta, ratio

    if mejor_ratio >= 0.8:
        return mejor, mejor_ratio
    return None, mejor_ratio


# ---------------------------------------------------------------------------
# LECTURA DE LAS MATERIAS DEL ALUMNO
# ---------------------------------------------------------------------------

_PALABRAS_NOTA = {
    "CERO": 0, "UNO": 1, "DOS": 2, "TRES": 3, "CUATRO": 4, "CINCO": 5,
    "SEIS": 6, "SIETE": 7, "OCHO": 8, "NUEVE": 9, "DIEZ": 10,
}

APROBADA, DESAPROBADA, REVISAR = "aprobada", "desaprobada", "revisar"


def estado_de_la_nota(nota):
    """Dice si la calificación es de aprobada, de desaprobada o hay que mirarla.

    Acepta '7 (SIETE)', 'SIETE (7)', 'Aprobado', 'APROBADO POR RESOLUCION ...',
    'Ausente' y las celdas vacías.
    """
    t = normalizar(nota)
    if not t:
        return REVISAR
    if "AUSENTE" in t:
        return DESAPROBADA
    if t.startswith("APROBAD") or "EQUIVALENCIA" in t or "RESOLUCION" in t:
        return APROBADA

    numeros = re.findall(r'\d+', t)
    if numeros:
        valores = [int(n) for n in numeros if int(n) <= 10]
        if valores:
            return APROBADA if max(valores) >= NOTA_MINIMA else DESAPROBADA

    for palabra in t.split():
        if palabra in _PALABRAS_NOTA:
            return APROBADA if _PALABRAS_NOTA[palabra] >= NOTA_MINIMA else DESAPROBADA

    return REVISAR


def es_actividad_electiva(nombre):
    clave = normalizar(nombre)
    return clave.startswith("ACTIVIDAD ELECTIVA") or clave.startswith("ELECTIVA")


def es_electiva_sin_nombre(nombre):
    """La electiva quedó con el texto del desplegable ('ESCRIBIR SU NOMBRE...'),
    o sea que todavía no le escribieron cuál es. Ese texto sale tal cual en el
    analítico, así que conviene avisarlo."""
    return "ESCRIBIR SU NOMBRE" in normalizar(nombre)


def horas_de(texto):
    """Saca el número de horas de una celda: '95', '95 hs', '95,5'."""
    t = (texto or "").replace(",", ".").strip()
    m = re.search(r'\d+(?:\.\d+)?', t)
    return float(m.group()) if m else 0.0


def sumar_horas_electivas(filas_editor):
    """Suma las horas de las filas que son actividades electivas.

    filas_editor es [(asignatura, horas)] o [(asignatura, horas, nota)] leído
    de la hoja EDITOR. Una electiva desaprobada o ausente no suma; si no se
    sabe la nota (no está esa columna), se cuenta igual.

    Devuelve (horas, cuántas, cuántas_sin_horas). Las horas se tipean a mano,
    así que las que quedaron en blanco se cuentan aparte: sin eso la suma da
    de menos y parecería que al alumno le faltan horas.
    """
    total, cuantas, sin_horas = 0.0, 0, 0
    for fila in filas_editor:
        asignatura, horas = fila[0], fila[1]
        nota = fila[2] if len(fila) > 2 else ""
        if not es_actividad_electiva(asignatura):
            continue
        if nota and estado_de_la_nota(nota) == DESAPROBADA:
            continue
        cuantas += 1
        hs = horas_de(horas)
        if hs:
            total += hs
        else:
            sin_horas += 1
    return total, cuantas, sin_horas


def armar_cursadas(filas):
    """De [(nombre, nota)] a la lista de materias del alumno, ya clasificadas."""
    cursadas = []
    for nombre, nota in filas:
        nombre = " ".join((nombre or "").split())
        nota = " ".join((nota or "").split())
        if not nombre:
            continue
        cursadas.append({
            "nombre": nombre,
            "clave": normalizar(nombre),
            "nota": nota,
            "estado": estado_de_la_nota(nota),
            "electiva": es_actividad_electiva(nombre),
        })
    return cursadas


# ---------------------------------------------------------------------------
# COMPARACIÓN
# ---------------------------------------------------------------------------

def materia_del_plan(plan, cursada):
    """A qué materia del plan corresponde una cursada. (materia, parecido).

    Sirve para los renglones que sobran: casi siempre son la misma materia
    rendida más de una vez (el aplazo o el ausente, y después la aprobada),
    no materias ajenas al plan.
    """
    for materia in plan["materias"]:
        if cursada["clave"] in materia.claves:
            return materia, 1.0

    mejor, mejor_ratio = None, 0
    for materia in plan["materias"]:
        if not materia.claves:
            continue
        ratio = max(parecido(clave, cursada["clave"]) for clave in materia.claves)
        if ratio > mejor_ratio:
            mejor, mejor_ratio = materia, ratio
    if mejor_ratio >= UMBRAL_PARECIDO:
        return mejor, mejor_ratio
    return None, mejor_ratio


def comparar(plan, cursadas, horas_electivas=None, electivas_sin_horas=0):
    """Cruza el plan con lo que rindió el alumno.

    horas_electivas es lo que suma la columna Hs. del EDITOR, para los planes
    que piden las electivas por carga horaria (ELECTIVAS_HS) en vez de por
    cantidad. Si no se pudo leer, o si quedaron electivas sin las horas
    tipeadas (electivas_sin_horas), el chequeo lo informa en vez de dar por
    faltante algo que no sabe.

    Para cada materia del plan busca primero el nombre igual (o alguno de sus
    alias) y, si no aparece, el nombre más parecido. Cuando una materia figura
    dos veces (la desaprobó y después la aprobó), se queda con la aprobada.
    """
    disponibles = [i for i, c in enumerate(cursadas) if not c["electiva"]]

    por_clave = {}
    for i in disponibles:
        por_clave.setdefault(cursadas[i]["clave"], []).append(i)

    usados = set()

    def tomar(indices):
        """De los candidatos libres, prefiere el que esté aprobado."""
        libres = [i for i in indices if i not in usados]
        if not libres:
            return None
        for estado in (APROBADA, REVISAR, DESAPROBADA):
            for i in libres:
                if cursadas[i]["estado"] == estado:
                    return i
        return libres[0]

    encontradas = {}          # índice de la materia del plan -> (cursada, ratio)
    sin_encontrar = []

    # 1) coincidencia exacta por nombre o alias
    for n, materia in enumerate(plan["materias"]):
        elegido = None
        for clave in materia.claves:
            elegido = tomar(por_clave.get(clave, []))
            if elegido is not None:
                break
        if elegido is None:
            sin_encontrar.append(n)
        else:
            usados.add(elegido)
            encontradas[n] = (elegido, 1.0)

    # 2) para las que quedaron, el nombre más parecido (se asigna el mejor par
    #    primero, así dos materias parecidas no se pisan)
    candidatos = []
    for n in sin_encontrar:
        materia = plan["materias"][n]
        for i in disponibles:
            if i in usados:
                continue
            ratio = max(parecido(clave, cursadas[i]["clave"]) for clave in materia.claves)
            if ratio >= UMBRAL_PARECIDO:
                candidatos.append((ratio, n, i))

    candidatos.sort(reverse=True)
    for ratio, n, i in candidatos:
        if n in encontradas or i in usados:
            continue
        usados.add(i)
        encontradas[n] = (i, ratio)

    # 3) armar el resultado
    resultado = {
        "plan": plan,
        "aprobadas": [],
        "faltantes": [],          # obligatorias que no figuran en el analítico
        "pendientes": [],         # figuran, pero desaprobadas o ausentes
        "aproximadas": [],        # coincidieron por parecido: conviene mirarlas
        "sin_nota": [],           # figuran, pero no se entiende la calificación
        "repetidas": [],          # rendidas más de una vez (aplazos, ausentes)
        "optativas_faltantes": [],
        "fuera_del_plan": [],
        "electivas": {"pide": plan.get("electivas", 0),
                      "pide_hs": plan.get("electivas_hs", 0),
                      "tiene": 0, "horas": horas_electivas,
                      "sin_horas": electivas_sin_horas, "sin_nombre": 0,
                      "aprobadas": [], "otras": []},
    }

    for n, materia in enumerate(plan["materias"]):
        if n not in encontradas:
            if materia.obligatoria:
                resultado["faltantes"].append(materia)
            else:
                resultado["optativas_faltantes"].append(materia)
            continue

        i, ratio = encontradas[n]
        cursada = cursadas[i]
        par = (materia, cursada, ratio)
        if ratio < 1.0:
            resultado["aproximadas"].append(par)
        if cursada["estado"] == APROBADA:
            resultado["aprobadas"].append(par)
        elif cursada["estado"] == DESAPROBADA:
            resultado["pendientes"].append(par)
        else:
            resultado["sin_nota"].append(par)

    for i, cursada in enumerate(cursadas):
        if cursada["electiva"]:
            if es_electiva_sin_nombre(cursada["nombre"]):
                resultado["electivas"]["sin_nombre"] += 1
            if cursada["estado"] == APROBADA:
                resultado["electivas"]["tiene"] += 1
                resultado["electivas"]["aprobadas"].append(cursada)
            else:
                resultado["electivas"]["otras"].append(cursada)
        elif i not in usados:
            # Antes de darla por ajena al plan, fijarse si es la misma materia
            # rendida otra vez: el aplazo o el ausente de una que ya aprobó.
            materia, ratio = materia_del_plan(plan, cursada)
            if materia is not None:
                resultado["repetidas"].append((materia, cursada, ratio))
            else:
                resultado["fuera_del_plan"].append(cursada)

    electivas = resultado["electivas"]
    resultado["faltan_electivas"] = max(0, electivas["pide"] - electivas["tiene"])

    # Electivas por carga horaria. Si el plan las pide y no se pudieron leer
    # las horas, no se cuenta como que falten: se avisa para que lo mires.
    resultado["faltan_horas_electivas"] = 0
    resultado["horas_electivas_sin_leer"] = False
    if electivas["pide_hs"]:
        if horas_electivas and not electivas_sin_horas:
            resultado["faltan_horas_electivas"] = max(
                0, electivas["pide_hs"] - horas_electivas)
        else:
            # O no se pudo leer la columna, o hay electivas a las que todavía
            # no les tipearon las horas: se avisa, no se da por faltante.
            resultado["horas_electivas_sin_leer"] = True

    resultado["ok"] = (not resultado["faltantes"]
                       and not resultado["pendientes"]
                       and not resultado["sin_nota"]
                       and resultado["faltan_electivas"] == 0
                       and resultado["faltan_horas_electivas"] == 0)
    return resultado


# ---------------------------------------------------------------------------
# INFORME
# ---------------------------------------------------------------------------

def _lista(materias, limite=12):
    nombres = [m.nombre if isinstance(m, MateriaPlan) else m for m in materias]
    if len(nombres) > limite:
        resto = len(nombres) - limite
        nombres = nombres[:limite] + ["... y %d más (ver la hoja '%s')"
                                      % (resto, NOMBRE_HOJA_INFORME)]
    return "\n".join("   \u2022 " + n for n in nombres)


def _plural(cantidad, singular, plural):
    return "%d %s" % (cantidad, singular if cantidad == 1 else plural)


def armar_resumen(alumno, resultado, femenino=False):
    """El cartel que ve el usuario."""
    plan = resultado["plan"]
    electivas = resultado["electivas"]
    total = len(plan["materias"])
    obligatorias = sum(1 for m in plan["materias"] if m.obligatoria)
    quien = alumno or ("La alumna" if femenino else "El alumno")
    aprobade = "aprobada" if femenino else "aprobado"

    partes = []
    if resultado["ok"]:
        detalle = ("tiene aprobadas las %s obligatorias del plan"
                   % _plural(obligatorias, "materia", "materias"))
        if electivas["pide_hs"]:
            detalle += (" y %g hs de actividades electivas (el plan pide %g)"
                        % (electivas["horas"] or 0, electivas["pide_hs"]))
        elif electivas["pide"]:
            detalle += (" y %s" % _plural(electivas["tiene"], "actividad electiva",
                                          "actividades electivas"))
        partes.append("%s está %s y no le faltan materias:\n%s."
                      % (quien, aprobade, detalle))
    else:
        pedazos = []
        if resultado["faltantes"]:
            pedazos.append(_plural(len(resultado["faltantes"]),
                                   "materia sin rendir", "materias sin rendir"))
        if resultado["pendientes"]:
            pedazos.append(_plural(len(resultado["pendientes"]),
                                   "desaprobada o ausente", "desaprobadas o ausentes"))
        if resultado["faltan_electivas"]:
            pedazos.append(_plural(resultado["faltan_electivas"],
                                   "actividad electiva", "actividades electivas"))
        if resultado["faltan_horas_electivas"]:
            pedazos.append("%g hs de actividades electivas"
                           % resultado["faltan_horas_electivas"])
        if resultado["sin_nota"]:
            pedazos.append("%d sin calificación clara" % len(resultado["sin_nota"]))
        partes.append("A %s le falta%s: %s."
                      % (quien, "" if len(pedazos) == 1 else "n", ", ".join(pedazos)))

    if electivas["sin_nombre"]:
        partes.append(
            "OJO: hay %s sin el nombre escrito (quedó el texto del "
            "desplegable). Completalo en el EDITOR: ese texto sale tal cual "
            "en el analítico."
            % _plural(electivas["sin_nombre"], "actividad electiva",
                      "actividades electivas"))

    if resultado["horas_electivas_sin_leer"]:
        if electivas["sin_horas"]:
            partes.append(
                "OJO: hay %s sin las horas cargadas en la columna Hs. del "
                "EDITOR. El plan pide %g hs: completalas y volvé a chequear."
                % (_plural(electivas["sin_horas"], "actividad electiva",
                           "actividades electivas"), electivas["pide_hs"]))
        else:
            partes.append("OJO: el plan pide %g hs de actividades electivas y no "
                          "pude leer la columna Hs. del EDITOR. Revisalo a mano."
                          % electivas["pide_hs"])

    resumen_plan = "Plan: %s\n(%d materias" % (plan["titulo"], total)
    if obligatorias != total:
        resumen_plan += ", %d obligatorias" % obligatorias
    if electivas["pide"]:
        resumen_plan += ", %d electivas" % electivas["pide"]
    if electivas["pide_hs"]:
        resumen_plan += ", %g hs de electivas" % electivas["pide_hs"]
    partes.append(resumen_plan + ")")

    if resultado["faltantes"]:
        partes.append("NO FIGURAN EN EL ANALÍTICO:\n" + _lista(resultado["faltantes"]))
    if resultado["pendientes"]:
        partes.append("DESAPROBADAS O AUSENTES:\n"
                      + _lista(["%s (%s)" % (m.nombre, c["nota"] or "sin nota")
                                for m, c, _ in resultado["pendientes"]]))
    if resultado["sin_nota"]:
        partes.append("SIN CALIFICACIÓN CLARA:\n"
                      + _lista([m.nombre for m, _, _ in resultado["sin_nota"]]))
    if resultado["aproximadas"]:
        partes.append("COINCIDENCIAS APROXIMADAS (revisá que sean la misma materia):\n"
                      + _lista(["%s  =  %s" % (m.nombre, c["nombre"])
                                for m, c, _ in resultado["aproximadas"]]))
    if resultado["repetidas"]:
        partes.append(
            "RENDIDAS MÁS DE UNA VEZ (aplazos o ausentes previos; se tomó la "
            "aprobada, no bloquean):\n"
            + _lista(["%s (%s)" % (m.nombre, c["nota"] or "sin nota")
                      for m, c, _ in resultado["repetidas"]]))

    if resultado["electivas"]["otras"]:
        partes.append("ACTIVIDADES ELECTIVAS NO APROBADAS:\n"
                      + _lista(["%s (%s)" % (c["nombre"], c["nota"] or "sin nota")
                                for c in resultado["electivas"]["otras"]]))

    if resultado["optativas_faltantes"]:
        partes.append("MATERIAS NO OBLIGATORIAS QUE NO RINDIÓ (no bloquean):\n"
                      + _lista(resultado["optativas_faltantes"]))
    if resultado["fuera_del_plan"]:
        partes.append("EN EL ANALÍTICO PERO NO EN EL PLAN:\n"
                      + _lista([c["nombre"] for c in resultado["fuera_del_plan"]]))

    partes.append("El detalle completo quedó en la hoja '%s'." % NOMBRE_HOJA_INFORME)
    return "\n\n".join(partes)


ENCABEZADO_INFORME = ["Estado", "Materia del plan", "Año / Grupo",
                      "Como figura en el analítico", "Calificación", "Observación"]


def armar_detalle(resultado):
    """Las filas que se escriben en la hoja de informe."""
    filas = [ENCABEZADO_INFORME]
    plan = resultado["plan"]

    por_materia = {}
    for clave, etiqueta in (("aprobadas", "APROBADA"),
                            ("pendientes", "DESAPROBADA / AUSENTE"),
                            ("sin_nota", "REVISAR NOTA")):
        for materia, cursada, ratio in resultado[clave]:
            por_materia[materia.orden] = (etiqueta, cursada, ratio)

    # Los intentos anteriores van pegados abajo de su materia.
    repetidas_por_materia = {}
    for materia, cursada, ratio in resultado["repetidas"]:
        repetidas_por_materia.setdefault(materia.orden, []).append((cursada, ratio))

    for materia in plan["materias"]:
        datos = por_materia.get(materia.orden)
        if datos is None:
            etiqueta = "FALTA" if materia.obligatoria else "FALTA (no obligatoria)"
            filas.append([etiqueta, materia.nombre, materia.grupo, "", "", ""])
        else:
            etiqueta, cursada, ratio = datos
            observacion = ""
            if ratio < 1.0:
                observacion = ("Coincidencia aproximada (%d%%): revisar"
                               % round(ratio * 100))
            filas.append([etiqueta, materia.nombre, materia.grupo,
                          cursada["nombre"], cursada["nota"], observacion])

        for cursada, ratio in repetidas_por_materia.get(materia.orden, []):
            observacion = "Rendida más de una vez; vale la aprobada"
            if ratio < 1.0:
                observacion += " (coincidencia aproximada %d%%)" % round(ratio * 100)
            filas.append(["INTENTO ANTERIOR", materia.nombre, materia.grupo,
                          cursada["nombre"], cursada["nota"], observacion])

    electivas = resultado["electivas"]
    if electivas["pide"] or electivas["pide_hs"] or electivas["aprobadas"] \
            or electivas["otras"]:
        for cursada in electivas["aprobadas"]:
            filas.append(["APROBADA", "(actividad electiva)", "",
                          cursada["nombre"], cursada["nota"],
                          "Falta escribir el nombre de la actividad"
                          if es_electiva_sin_nombre(cursada["nombre"]) else ""])
        for cursada in electivas["otras"]:
            filas.append(["REVISAR" if cursada["estado"] == REVISAR else "DESAPROBADA",
                          "(actividad electiva)", "", cursada["nombre"],
                          cursada["nota"], "No cuenta como aprobada"])
        for _ in range(resultado["faltan_electivas"]):
            filas.append(["FALTA", "(actividad electiva)", "", "", "",
                          "El plan pide %d" % electivas["pide"]])
        if electivas["pide_hs"]:
            if resultado["horas_electivas_sin_leer"]:
                estado = "REVISAR"
                observacion = ("Faltan tipear las horas de %d electiva(s)"
                               % electivas["sin_horas"]) if electivas["sin_horas"] \
                    else "No pude leer la columna Hs. del EDITOR"
            elif resultado["faltan_horas_electivas"]:
                estado = "FALTA"
                observacion = ("Faltan %g hs"
                               % resultado["faltan_horas_electivas"])
            else:
                estado, observacion = "APROBADA", ""
            filas.append([estado, "(horas de electivas: %g de %g)"
                          % (electivas["horas"] or 0, electivas["pide_hs"]),
                          "", "", "", observacion])

    for cursada in resultado["fuera_del_plan"]:
        filas.append(["FUERA DEL PLAN", "", "", cursada["nombre"], cursada["nota"],
                      "No figura en el plan de estudios"])
    return filas


# ---------------------------------------------------------------------------
# LIBREOFFICE (UNO)
# ---------------------------------------------------------------------------

def _msgbox(texto, titulo="Chequeo del plan de estudios", tipo="INFOBOX"):
    import uno
    ctx = uno.getComponentContext()
    tk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    return tk.createMessageBox(
        None, uno.Enum("com.sun.star.awt.MessageBoxType", tipo),
        1, titulo, texto).execute()


def _documento_actual():
    import uno
    ctx = uno.getComponentContext()
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx)
    return desktop.getCurrentComponent()


def _celda(doc, hoja, ref):
    try:
        return doc.getSheets().getByName(hoja).getCellRangeByName(ref).getString().strip()
    except Exception:
        return ""


def _carpeta_del_ods(doc):
    try:
        import uno
        url = doc.getURL()
        if url:
            return os.path.dirname(uno.fileUrlToSystemPath(url))
    except Exception:
        pass
    return None


def leer_materias_del_documento(doc):
    """Saca (nombre, nota) de la hoja 'Datos' o, si está vacía, de 'Extractor'.

    Devuelve (filas, nombre_de_la_hoja_usada).
    """
    hojas = doc.getSheets()

    if hojas.hasByName(HOJA_DATOS):
        hoja = hojas.getByName(HOJA_DATOS)
        filas, vacias = [], 0
        for f in range(PRIMERA_FILA_DATOS - 1, ULTIMA_FILA_DATOS):
            nombre = hoja.getCellByPosition(COL_NOMBRE_DATOS, f).getString().strip()
            nota = hoja.getCellByPosition(COL_NOTA_DATOS, f).getString().strip()
            if not nombre:
                vacias += 1
                if vacias >= 10:
                    break
                continue
            vacias = 0
            filas.append((nombre, nota))
        if filas:
            return filas, HOJA_DATOS

    if hojas.hasByName(HOJA_EXTRACTOR):
        hoja = hojas.getByName(HOJA_EXTRACTOR)
        filas, vacias = [], 0
        for f in range(0, ULTIMA_FILA_DATOS):
            nombre = hoja.getCellByPosition(COL_NOMBRE_EXTRACTOR, f).getString().strip()
            nota = hoja.getCellByPosition(COL_NOTA_EXTRACTOR, f).getString().strip()
            if not nombre:
                vacias += 1
                if vacias >= 10:
                    break
                continue
            vacias = 0
            filas.append((nombre, nota))
        if filas:
            return filas, HOJA_EXTRACTOR

    return [], ""


def columna_por_encabezado(encabezados, prefijos, por_defecto):
    """Busca en el encabezado del EDITOR la columna que empieza con alguno de
    esos prefijos ('Hs.', 'CALIFICACIÓN'). Solo mira de las asignaturas a la
    derecha, para no confundirse con la parte de arriba de la hoja."""
    for c in range(COL_ASIGNATURA_EDITOR, len(encabezados)):
        titulo = normalizar(encabezados[c])
        if titulo and any(titulo.startswith(p) for p in prefijos):
            return c
    return por_defecto


def leer_filas_editor(doc):
    """(asignatura, horas, nota) de la hoja EDITOR: de ahí salen las horas de
    las actividades electivas, que la tabla de 'Datos' no arrastra."""
    hojas = doc.getSheets()
    if not hojas.hasByName(HOJA_EDITOR):
        return []
    hoja = hojas.getByName(HOJA_EDITOR)

    encabezados = [hoja.getCellByPosition(c, FILA_ENCABEZADO_EDITOR).getString()
                   for c in range(COL_ASIGNATURA_EDITOR + 12)]
    col_hs = columna_por_encabezado(encabezados, PREFIJOS_HS, COL_HS_EDITOR)
    col_nota = columna_por_encabezado(encabezados, PREFIJOS_NOTA, None)

    def texto(c, f):
        celda = hoja.getCellByPosition(c, f)
        t = celda.getString().strip()
        if not t:
            valor = celda.getValue()
            t = str(valor) if valor else ""
        return t

    filas, vacias = [], 0
    for f in range(PRIMERA_FILA_EDITOR, ULTIMA_FILA_DATOS):
        nombre = hoja.getCellByPosition(COL_ASIGNATURA_EDITOR, f).getString().strip()
        if not nombre:
            vacias += 1
            if vacias >= 10:
                break
            continue
        vacias = 0
        filas.append((nombre, texto(col_hs, f),
                      texto(col_nota, f) if col_nota is not None else ""))
    return filas


# Qué se borra al limpiar: valores, fechas, texto y fórmulas.
# (com.sun.star.sheet.CellFlags: VALUE 1 + DATETIME 2 + STRING 4 + FORMULA 16)
BORRAR_CONTENIDO = 1 + 2 + 4 + 16


def vaciar_hoja_informe(hoja):
    """Borra todo lo escrito en la hoja del chequeo anterior.

    Se mira el área realmente usada, así no queda nada colgado del informe de
    otro alumno aunque el anterior haya sido más largo que éste.
    """
    try:
        cursor = hoja.createCursor()
        cursor.gotoEndOfUsedArea(False)
        direccion = cursor.getRangeAddress()
        ultima_fila, ultima_col = direccion.EndRow, direccion.EndColumn
    except Exception:
        ultima_fila, ultima_col = ULTIMA_FILA_DATOS + 40, len(ENCABEZADO_INFORME) - 1

    if ultima_fila < 0 or ultima_col < 0:
        return
    hoja.getCellRangeByPosition(0, 0, ultima_col, ultima_fila).clearContents(
        BORRAR_CONTENIDO)


def escribir_informe(doc, filas, resumen, encabezado=""):
    """Deja el detalle en la hoja de informe (la crea si no está)."""
    hojas = doc.getSheets()
    if not hojas.hasByName(NOMBRE_HOJA_INFORME):
        hojas.insertNewByName(NOMBRE_HOJA_INFORME, hojas.getCount())
    hoja = hojas.getByName(NOMBRE_HOJA_INFORME)

    vaciar_hoja_informe(hoja)

    ancho = len(ENCABEZADO_INFORME)
    cuerpo = []
    if encabezado:
        cuerpo.append([encabezado] + [""] * (ancho - 1))
    cuerpo += [[resumen.replace("\n", " ").replace("\u2022", "-")] + [""] * (ancho - 1),
               [""] * ancho] + [list(f) for f in filas]
    hoja.getCellRangeByPosition(0, 0, ancho - 1, len(cuerpo) - 1).setDataArray(
        tuple(tuple(c for c in fila) for fila in cuerpo))


def _elegir_plan_a_mano(carpetas):
    """Abre el diálogo de archivos para elegir el plan a mano."""
    import uno
    ctx = uno.getComponentContext()
    picker = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.ui.dialogs.FilePicker", ctx)
    picker.setTitle("Elegir el plan de estudios")
    picker.appendFilter("Planes de estudio (*.txt; *.csv)", "*.txt;*.csv")
    if carpetas:
        try:
            picker.setDisplayDirectory(
                "file:///" + carpetas[0].replace("\\", "/").lstrip("/"))
        except Exception:
            pass
    if picker.execute() != 1:
        return None
    archivos = picker.getFiles()
    if not archivos:
        return None
    return uno.fileUrlToSystemPath(archivos[0])


def chequear_documento(doc, avisar=True):
    """El chequeo en sí. Devuelve el resultado, o None si no se pudo hacer."""
    carrera = _celda(doc, *CELDA_CARRERA)
    apellido = _celda(doc, *CELDA_APELLIDO)
    nombres = _celda(doc, *CELDA_NOMBRES)
    alumno = ", ".join([p for p in (apellido, nombres) if p])
    femenino = "SRTA" in normalizar(_celda(doc, *CELDA_GENERO))

    carpetas = buscar_carpetas_de_planes(_carpeta_del_ods(doc))
    if not carpetas:
        if avisar:
            _msgbox("No encontré la carpeta con los planes de estudio.\n\n"
                    "Creá una carpeta que se llame 'Planes de estudio' al lado "
                    "del generador (el .ods) y poné adentro un archivo de texto "
                    "por carrera.", tipo="WARNINGBOX")
        return None

    ruta_plan, exactitud = buscar_plan_de_carrera(carrera, carpetas)
    if ruta_plan is None:
        disponibles = [os.path.basename(a) for a in archivos_de_plan(carpetas)]
        texto = ("No encontré el plan de la carrera '%s'.\n\n"
                 "Planes cargados:\n%s\n"
                 % (carrera or "(Datos!AZ3 está vacía)",
                    "\n".join("   \u2022 " + d for d in disponibles) or "   (ninguno)"))
        texto += ("\nPara cargarlo, con la carrera elegida en el EDITOR corré la "
                  "macro ImportarPlanDeLaPlanilla: arma el plan con la lista de "
                  "materias que ya tiene la planilla.")
        pdf = buscar_pdf_de_carrera(carrera, carpetas)
        if pdf:
            texto += ("\nTambién está el PDF del plan ('%s'): si esa carrera no "
                      "tiene la lista cargada, usá ImportarPlanPDF."
                      % os.path.basename(pdf))
        texto += "\n\nMientras tanto, podés elegir el plan a mano."
        if not avisar:
            return None
        _msgbox(texto, tipo="WARNINGBOX")
        ruta_plan = _elegir_plan_a_mano(carpetas)
        if not ruta_plan:
            return None
        exactitud = 1.0          # lo eligió el usuario: no hay nada que avisar

    try:
        plan = leer_plan(ruta_plan)
    except Exception as e:
        if avisar:
            _msgbox("No pude leer el plan:\n%s\n\n%s" % (ruta_plan, e), tipo="ERRORBOX")
        return None

    if not plan["materias"]:
        if avisar:
            _msgbox("El plan '%s' no tiene ninguna materia cargada."
                    % os.path.basename(ruta_plan), tipo="WARNINGBOX")
        return None

    filas, hoja_usada = leer_materias_del_documento(doc)
    if not filas:
        if avisar:
            _msgbox("No encontré materias en las hojas '%s' ni '%s'."
                    % (HOJA_DATOS, HOJA_EXTRACTOR), tipo="WARNINGBOX")
        return None

    # Las horas de electivas solo se leen si el plan las pide así.
    horas_electivas, electivas_sin_horas = None, 0
    if plan.get("electivas_hs"):
        try:
            horas_electivas, _, electivas_sin_horas = sumar_horas_electivas(
                leer_filas_editor(doc))
            horas_electivas = horas_electivas or None
        except Exception:
            horas_electivas, electivas_sin_horas = None, 0

    resultado = comparar(plan, armar_cursadas(filas), horas_electivas,
                         electivas_sin_horas)
    resumen = armar_resumen(alumno, resultado, femenino)

    aviso = ""
    if exactitud and exactitud < 1.0:
        aviso = ("\n\nOJO: usé el plan '%s' porque es el más parecido a '%s'."
                 % (os.path.basename(ruta_plan), carrera))
    resumen_completo = resumen + ("\n\n(Materias leídas de la hoja '%s'.)" % hoja_usada) + aviso

    encabezado = "Chequeo del %s \u2013 %s%s" % (
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        alumno or "(sin nombre)",
        " \u2013 %s" % carrera if carrera else "")
    try:
        escribir_informe(doc, armar_detalle(resultado), resumen, encabezado)
    except Exception as e:
        resumen_completo += "\n\n(No pude escribir la hoja de detalle: %s)" % e

    if avisar:
        _msgbox(resumen_completo,
                tipo="INFOBOX" if resultado["ok"] else "WARNINGBOX")
    return resultado


def ChequearPlan(*args):
    """Botón del .ods: chequea el analítico abierto contra el plan de estudios."""
    doc = _documento_actual()
    if doc is None or not hasattr(doc, "getSheets"):
        _msgbox("Abrí el generador (.ods) y probá de nuevo.", tipo="ERRORBOX")
        return
    chequear_documento(doc)


def LimpiarChequeo(*args):
    """Botón / macro: deja la hoja 'Chequeo' en blanco.

    No hace falta correrla para chequear otro alumno (el informe se reescribe
    entero cada vez); es para dejar la planilla limpia al terminar.
    """
    doc = _documento_actual()
    if doc is None or not hasattr(doc, "getSheets"):
        _msgbox("Abrí el generador (.ods) y probá de nuevo.", tipo="ERRORBOX")
        return

    hojas = doc.getSheets()
    if not hojas.hasByName(NOMBRE_HOJA_INFORME):
        _msgbox("No hay ninguna hoja '%s' para limpiar." % NOMBRE_HOJA_INFORME)
        return

    vaciar_hoja_informe(hojas.getByName(NOMBRE_HOJA_INFORME))
    _msgbox("La hoja '%s' quedó vacía." % NOMBRE_HOJA_INFORME)


g_exportedScripts = (ChequearPlan, LimpiarChequeo)


# ---------------------------------------------------------------------------
# MODO TERMINAL (para probar sin abrir LibreOffice)
# ---------------------------------------------------------------------------

def _grillas_de_ods(ruta_ods):
    """Lee un .ods guardado y devuelve {hoja: [[celda, ...], ...]}."""
    import zipfile
    from xml.etree import ElementTree as ET

    NS = {"table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
          "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
          "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}

    def q(t):
        prefijo, local = t.split(":")
        return "{%s}%s" % (NS[prefijo], local)

    with zipfile.ZipFile(ruta_ods) as z:
        raiz = ET.fromstring(z.read("content.xml"))

    hojas = {}
    cuerpo = raiz.find(q("office:body")).find(q("office:spreadsheet"))
    for tabla in cuerpo.findall(q("table:table")):
        grilla = []
        for r in tabla.findall(q("table:table-row")):
            repetir = min(int(r.get(q("table:number-rows-repeated")) or 1), 1000)
            fila = []
            for c in list(r):
                if c.tag not in (q("table:table-cell"), q("table:covered-table-cell")):
                    continue
                crep = min(int(c.get(q("table:number-columns-repeated")) or 1), 40)
                texto = "\n".join("".join(p.itertext()) for p in c.iter(q("text:p")))
                fila.extend([texto] * crep)
            grilla.extend([fila] * repetir)
        hojas[tabla.get(q("table:name"))] = grilla
    return hojas


def _celda_de_grilla(grilla, fila, col):
    if fila < len(grilla) and col < len(grilla[fila]):
        return (grilla[fila][col] or "").strip()
    return ""


def leer_materias_de_ods(ruta_ods, hojas=None):
    """Lee (nombre, nota) de un .ods guardado, sin LibreOffice."""
    hojas = hojas if hojas is not None else _grillas_de_ods(ruta_ods)

    def columna(grilla, fila, col):
        return _celda_de_grilla(grilla, fila, col)

    for hoja, primera, col_nombre, col_nota in (
            (HOJA_DATOS, PRIMERA_FILA_DATOS - 1, COL_NOMBRE_DATOS, COL_NOTA_DATOS),
            (HOJA_EXTRACTOR, 0, COL_NOMBRE_EXTRACTOR, COL_NOTA_EXTRACTOR)):
        grilla = hojas.get(hoja)
        if not grilla:
            continue
        filas, vacias = [], 0
        for f in range(primera, min(len(grilla), ULTIMA_FILA_DATOS)):
            nombre = columna(grilla, f, col_nombre)
            if not nombre:
                vacias += 1
                if vacias >= 10:
                    break
                continue
            vacias = 0
            filas.append((nombre, columna(grilla, f, col_nota)))
        if filas:
            return filas, hoja
    return [], ""


def leer_filas_editor_de_ods(hojas):
    """(asignatura, horas, nota) de la hoja EDITOR de un .ods guardado."""
    grilla = hojas.get(HOJA_EDITOR)
    if not grilla:
        return []

    encabezados = [_celda_de_grilla(grilla, FILA_ENCABEZADO_EDITOR, c)
                   for c in range(COL_ASIGNATURA_EDITOR + 12)]
    col_hs = columna_por_encabezado(encabezados, PREFIJOS_HS, COL_HS_EDITOR)
    col_nota = columna_por_encabezado(encabezados, PREFIJOS_NOTA, None)

    filas, vacias = [], 0
    for f in range(PRIMERA_FILA_EDITOR, min(len(grilla), ULTIMA_FILA_DATOS)):
        nombre = _celda_de_grilla(grilla, f, COL_ASIGNATURA_EDITOR)
        if not nombre:
            vacias += 1
            if vacias >= 10:
                break
            continue
        vacias = 0
        filas.append((nombre, _celda_de_grilla(grilla, f, col_hs),
                      _celda_de_grilla(grilla, f, col_nota)
                      if col_nota is not None else ""))
    return filas


def leer_materias_de_texto(ruta):
    """Archivo de prueba: 'MATERIA | NOTA' por renglón."""
    filas = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            partes = [p.strip() for p in linea.split("|")]
            filas.append((partes[0], partes[1] if len(partes) > 1 else ""))
    return filas, os.path.basename(ruta)


def main(argv):
    if len(argv) < 3:
        print("Uso: python3 ChequearPlan.py <plan.txt> <planilla.ods | materias.txt> "
              "[Apellido, Nombres]")
        return 2

    plan = leer_plan(argv[1])
    origen = argv[2]
    horas_electivas = None
    femenino, electivas_sin_horas = False, 0
    if origen.lower().endswith(".ods"):
        hojas = _grillas_de_ods(origen)
        filas, hoja = leer_materias_de_ods(origen, hojas)
        col, fil = _ref_a_columna_fila(CELDA_GENERO[1])
        femenino = "SRTA" in normalizar(
            _celda_de_grilla(hojas.get(CELDA_GENERO[0], []), fil, col))
        if plan.get("electivas_hs"):
            horas_electivas, _, electivas_sin_horas = sumar_horas_electivas(
                leer_filas_editor_de_ods(hojas))
            horas_electivas = horas_electivas or None
    else:
        filas, hoja = leer_materias_de_texto(origen)

    if not filas:
        print("No encontré materias en %s" % origen)
        return 1

    resultado = comparar(plan, armar_cursadas(filas), horas_electivas,
                         electivas_sin_horas)
    print(armar_resumen(argv[3] if len(argv) > 3 else "", resultado, femenino))
    print("\n(Materias leídas de '%s': %d)" % (hoja, len(filas)))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
