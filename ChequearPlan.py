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


_DIRECTIVA_RE = re.compile(r'^(TITULO|T[ÍI]TULO|ELECTIVAS)\s*:\s*(.*)$', re.IGNORECASE)


def leer_plan(ruta):
    """Lee un archivo de plan de estudios y devuelve sus materias.

    Formato (texto plano, un archivo por carrera):

        # lo que empieza con # es un comentario
        TITULO: Tecnicatura Superior en Enfermería (Res. 123/15)
        ELECTIVAS: 2

        [Primer año]
        ANATOMIA Y FISIOLOGIA | ANATOMOFISIOLOGIA
        ENFERMERIA BASICA
        ? SEMINARIO DE INGLES        <- el "?" adelante = no es obligatoria

    Lo que va después de "|" son nombres alternativos: sirve para cuando el
    analítico escribe la materia distinto que el plan.
    """
    texto = None
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(ruta, "r", encoding=codificacion) as f:
                texto = f.read()
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise IOError("No se pudo leer el plan: %s" % ruta)

    plan = {"ruta": ruta, "titulo": "", "electivas": 0, "materias": []}
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
            if clave == "TITULO":
                plan["titulo"] = valor
            else:
                numeros = re.search(r'\d+', valor)
                plan["electivas"] = int(numeros.group()) if numeros else 0
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
        plan["titulo"] = os.path.splitext(os.path.basename(ruta))[0]
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


def buscar_plan_de_carrera(carrera, carpetas):
    """Elige el archivo de plan que corresponde a la carrera.

    Devuelve (ruta, exactitud) o (None, 0). La exactitud es 1 cuando el nombre
    del archivo coincide con la carrera y menos cuando es un parecido.
    """
    clave_carrera = normalizar(carrera)
    if not clave_carrera:
        return None, 0

    mejor, mejor_ratio = None, 0
    for ruta in archivos_de_plan(carpetas):
        clave_archivo = normalizar(os.path.splitext(os.path.basename(ruta))[0])
        if not clave_archivo:
            continue
        if clave_archivo == clave_carrera:
            return ruta, 1.0
        if clave_carrera in clave_archivo or clave_archivo in clave_carrera:
            ratio = 0.95
        else:
            ratio = parecido(clave_archivo, clave_carrera)
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

def comparar(plan, cursadas):
    """Cruza el plan con lo que rindió el alumno.

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
        "optativas_faltantes": [],
        "fuera_del_plan": [],
        "electivas": {"pide": plan.get("electivas", 0), "tiene": 0, "nombres": []},
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
            if cursada["estado"] == APROBADA:
                resultado["electivas"]["tiene"] += 1
                resultado["electivas"]["nombres"].append(cursada["nombre"])
        elif i not in usados:
            resultado["fuera_del_plan"].append(cursada)

    electivas = resultado["electivas"]
    resultado["faltan_electivas"] = max(0, electivas["pide"] - electivas["tiene"])
    resultado["ok"] = (not resultado["faltantes"]
                       and not resultado["pendientes"]
                       and not resultado["sin_nota"]
                       and resultado["faltan_electivas"] == 0)
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
        if electivas["pide"]:
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
        if resultado["sin_nota"]:
            pedazos.append("%d sin calificación clara" % len(resultado["sin_nota"]))
        partes.append("A %s le falta%s: %s."
                      % (quien, "" if len(pedazos) == 1 else "n", ", ".join(pedazos)))

    resumen_plan = "Plan: %s\n(%d materias" % (plan["titulo"], total)
    if obligatorias != total:
        resumen_plan += ", %d obligatorias" % obligatorias
    if electivas["pide"]:
        resumen_plan += ", %d electivas" % electivas["pide"]
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
    if resultado["optativas_faltantes"]:
        partes.append("OPTATIVAS DEL PLAN QUE NO RINDIÓ (no bloquean):\n"
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

    for materia in plan["materias"]:
        datos = por_materia.get(materia.orden)
        if datos is None:
            etiqueta = "FALTA" if materia.obligatoria else "FALTA (optativa)"
            filas.append([etiqueta, materia.nombre, materia.grupo, "", "", ""])
            continue
        etiqueta, cursada, ratio = datos
        observacion = ""
        if ratio < 1.0:
            observacion = "Coincidencia aproximada (%d%%): revisar" % round(ratio * 100)
        filas.append([etiqueta, materia.nombre, materia.grupo,
                      cursada["nombre"], cursada["nota"], observacion])

    electivas = resultado["electivas"]
    if electivas["pide"] or electivas["nombres"]:
        for nombre in electivas["nombres"]:
            filas.append(["APROBADA", "(actividad electiva)", "", nombre, "", ""])
        for _ in range(resultado["faltan_electivas"]):
            filas.append(["FALTA", "(actividad electiva)", "", "", "",
                          "El plan pide %d" % electivas["pide"]])

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


def escribir_informe(doc, filas, resumen):
    """Deja el detalle en la hoja de informe (la crea si no está)."""
    hojas = doc.getSheets()
    if not hojas.hasByName(NOMBRE_HOJA_INFORME):
        hojas.insertNewByName(NOMBRE_HOJA_INFORME, hojas.getCount())
    hoja = hojas.getByName(NOMBRE_HOJA_INFORME)

    # Limpiar lo del chequeo anterior
    ancho = len(ENCABEZADO_INFORME)
    hoja.getCellRangeByPosition(0, 0, ancho - 1, ULTIMA_FILA_DATOS + 40).setDataArray(
        tuple(tuple("" for _ in range(ancho)) for _ in range(ULTIMA_FILA_DATOS + 41)))

    cuerpo = [[resumen.replace("\n", " ").replace("\u2022", "-")] + [""] * (ancho - 1),
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


def chequear_documento(doc, avisar=True, avisar_si_no_hay_plan=True):
    """El chequeo en sí. Devuelve el resultado, o None si no se pudo hacer.

    avisar_si_no_hay_plan=False sirve para el chequeo automático que corre al
    final de la extracción: si todavía no hay carpeta de planes o no está el
    plan de esa carrera, se sale calladito en vez de tirar un cartel.
    """
    carrera = _celda(doc, *CELDA_CARRERA)
    apellido = _celda(doc, *CELDA_APELLIDO)
    nombres = _celda(doc, *CELDA_NOMBRES)
    alumno = ", ".join([p for p in (apellido, nombres) if p])
    femenino = "SRTA" in normalizar(_celda(doc, *CELDA_GENERO))

    carpetas = buscar_carpetas_de_planes(_carpeta_del_ods(doc))
    if not carpetas:
        if avisar and avisar_si_no_hay_plan:
            _msgbox("No encontré la carpeta con los planes de estudio.\n\n"
                    "Creá una carpeta que se llame 'Planes de estudio' al lado "
                    "del generador (el .ods) y poné adentro un archivo de texto "
                    "por carrera.", tipo="WARNINGBOX")
        return None

    ruta_plan, exactitud = buscar_plan_de_carrera(carrera, carpetas)
    if ruta_plan is None:
        disponibles = [os.path.basename(a) for a in archivos_de_plan(carpetas)]
        texto = ("No encontré el plan de la carrera '%s'.\n\n"
                 "Planes disponibles:\n%s\n\nElegilo a mano."
                 % (carrera or "(Datos!AZ3 está vacía)",
                    "\n".join("   \u2022 " + d for d in disponibles) or "   (ninguno)"))
        if not avisar or not avisar_si_no_hay_plan:
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

    resultado = comparar(plan, armar_cursadas(filas))
    resumen = armar_resumen(alumno, resultado, femenino)

    aviso = ""
    if exactitud and exactitud < 1.0:
        aviso = ("\n\nOJO: usé el plan '%s' porque es el más parecido a '%s'."
                 % (os.path.basename(ruta_plan), carrera))
    resumen_completo = resumen + ("\n\n(Materias leídas de la hoja '%s'.)" % hoja_usada) + aviso

    try:
        escribir_informe(doc, armar_detalle(resultado), resumen)
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


g_exportedScripts = (ChequearPlan,)


# ---------------------------------------------------------------------------
# MODO TERMINAL (para probar sin abrir LibreOffice)
# ---------------------------------------------------------------------------

def leer_materias_de_ods(ruta_ods):
    """Lee (nombre, nota) de un .ods guardado, sin LibreOffice."""
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

    def columna(grilla, fila, col):
        if fila < len(grilla) and col < len(grilla[fila]):
            return (grilla[fila][col] or "").strip()
        return ""

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
    if origen.lower().endswith(".ods"):
        filas, hoja = leer_materias_de_ods(origen)
    else:
        filas, hoja = leer_materias_de_texto(origen)

    if not filas:
        print("No encontré materias en %s" % origen)
        return 1

    resultado = comparar(plan, armar_cursadas(filas))
    print(armar_resumen(argv[3] if len(argv) > 3 else "", resultado))
    print("\n(Materias leídas de '%s': %d)" % (hoja, len(filas)))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
