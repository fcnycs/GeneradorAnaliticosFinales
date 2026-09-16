# -*- coding: utf-8 -*-
"""
Importar un plan de estudios (a un .txt que lee ChequearPlan.py)
================================================================
Dos formas de armar el plan de una carrera, según de dónde salga:

  ImportarPlanDeLaPlanilla()  <- la MÁS CONFIABLE
      Usa la lista de materias que la propia planilla tiene en Datos!AZ,
      la del desplegable de ASIGNATURAS. Elegí la carrera en el EDITOR y
      corré la macro: sale con los nombres escritos igual que en el
      analítico, así que no hay nada que emparejar después.

  ImportarPlanPDF()
      Para las carreras que no tienen la lista cargada en la planilla:
      lee el PDF del plan y saca las materias de ahí.

En los dos casos es un BORRADOR: hay que abrirlo y revisarlo una vez.

Revisar quiere decir: sacar lo que sobra, agregar lo que falte, y completar
ELECTIVAS: o ELECTIVAS_HS: si el plan pide actividades electivas. Después queda
hecho para siempre, salvo que cambie el plan.

Cuando importa de un PDF, deja también un "<nombre>.crudo.txt" con todo el texto
del PDF tal cual, para copiar y pegar de ahí si el borrador salió flojo.

Desde la terminal:
    python3 ImportarPlan.py plan.pdf [otro.pdf ...]
    python3 ImportarPlan.py --planilla GENERADOR.ods
"""

import os
import re
import sys
import unicodedata

# ---------------------------------------------------------------------------
# NORMALIZACIÓN (igual que en ChequearPlan.py, repetida a propósito para que
# esta macro funcione sola)
# ---------------------------------------------------------------------------

def sin_tildes(texto):
    descompuesto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# LA LISTA QUE YA TIENE LA PLANILLA (Datos!AZ)
# ---------------------------------------------------------------------------

HOJA_LISTA = "Datos"
COL_LISTA = 51                # Datos!AZ
FILA_CARRERA = 2              # Datos!AZ3: la carrera elegida en el EDITOR
PRIMERA_FILA_LISTA = 4        # Datos!AZ5 en adelante
ULTIMA_FILA_LISTA = 400

# Renglones de la lista que no son materias.
_NO_ES_MATERIA = ("SELECCION", "SELECCIONAR", "ACTIVIDAD ELECTIVA", "ELECTIVA",
                  "0", "")


def es_renglon_de_lista(texto):
    """¿Este renglón de Datos!AZ es una materia de verdad?"""
    t = " ".join((texto or "").split())
    if not t or t == "0" or t.startswith("#"):      # vacío, cero o #¡REF!
        return False
    plano = sin_tildes(t).upper()
    if plano in _NO_ES_MATERIA:
        return False
    # "ACTIVIDAD ELECTIVA: ESCRIBIR SU NOMBRE Y ..." es el renglón comodín
    # del desplegable, no una materia.
    if plano.startswith("ACTIVIDAD ELECTIVA") or plano.startswith("ELECTIVA"):
        return False
    return len(t) >= 4


def materias_de_la_lista(celdas):
    """De las celdas de Datos!AZ a la lista de materias, sin repetir."""
    materias, vistas = [], set()
    vacias = 0
    for celda in celdas:
        texto = " ".join((celda or "").split())
        if not texto or texto == "0":
            vacias += 1
            if vacias >= 15 and materias:
                break
            continue
        vacias = 0
        if not es_renglon_de_lista(texto):
            continue
        clave = sin_tildes(texto).upper()
        if clave in vistas:
            continue
        vistas.add(clave)
        materias.append(texto)
    return materias


# ---------------------------------------------------------------------------
# RECONOCER LOS RENGLONES DEL PLAN (cuando sale de un PDF)
# ---------------------------------------------------------------------------

# "PRIMER AÑO", "1° AÑO", "AÑO 2", "CICLO BASICO"
_ENCABEZADO_GRUPO_RE = re.compile(
    r'^\W*(?:'
    r'(PRIMER|SEGUNDO|TERCER|TERCERO|CUARTO|QUINTO|SEXTO)O?\s+A[NÑ]O'
    r'|(\d)\s*[°ºª]?\s*(?:ER|DO|RO|TO|MO|VO)?\s*A[NÑ]O'
    r'|A[NÑ]O\s+(\d)'
    r'|CICLO\s+[A-Z]+'
    r')\b', re.IGNORECASE)

# Renglones que seguro no son materias.
_BASURA = (
    "universidad", "facultad", "plan de estudio", "anexo", "resoluc",
    "pagina", "expediente", "ordenanza", "consejo", "rector", "decano",
    "carga horaria", "total de horas", "horas totales", "correlativ",
    "requisito", "condiciones de ingreso", "perfil del", "alcances del",
    "titulo que otorga", "titulos", "duracion de la carrera", "indice",
    "asignatura", "actividad curricular", "codigo", "regimen",
    "fundamentacion", "objetivos", "campo de",
    "observaciones", "denominacion", "modalidad", "distribucion",
    "el alumno", "el estudiante", "debera", "deberan", "acreditar",
)

# Renglones de una sola palabra que son de la planilla, no materias.
_UNA_PALABRA_BASURA = {
    "TOTAL", "TOTALES", "SUBTOTAL", "HORAS", "ASIGNATURAS", "MATERIAS",
    "ANUAL", "CUATRIMESTRAL", "OPTATIVAS", "ELECTIVAS", "OBSERVACIONES",
    "NOTAS", "REGIMEN", "CORRELATIVAS",
}

# Más de esto ya no es un nombre de materia, es una oración.
MAX_PALABRAS = 9

# Basura pegada al final del renglón: horas, régimen, correlativas.
_COLA_RE = re.compile(
    r'^(?:'
    r'\d+(?:[.,]\d+)?'                    # 96 / 4,5
    r'|\d*\s*(?:HS|HRS|H|HORAS)'          # 96HS / HS
    r'|ANUAL(?:ES)?|CUATRIMESTRAL(?:ES)?|SEMESTRAL(?:ES)?|BIMESTRAL(?:ES)?'
    r'|CUATR?|CUATRIM|SEM|SEMANAL(?:ES)?|[12]\s*[°ºª]'
    r'|TEORIC[AO]S?|PRACTIC[AO]S?|TEORICO-?PRACTIC[AO]S?|TALLER(?:ES)?'
    r'|[12]\s*[°ºª]?\s*C|C\s*[12]|1ER|2DO'
    r'|[A-Z]{1,3}-?\d{1,4}'               # códigos: MA-101, Q3
    r'|-+|\.+|\|+'
    r')$', re.IGNORECASE)

# Código al principio: "1.", "01 -", "12)", "MA-101", "1.2.3"
_CODIGO_ADELANTE_RE = re.compile(
    r'^\s*(?:\d{1,3}(?:[.\-)]\d{1,3})*\s*[.\-)]?\s+|[A-Z]{1,4}\s*-?\s*\d{1,4}\s+)',
    re.IGNORECASE)


def es_encabezado_de_grupo(linea):
    """Si el renglón es un encabezado ("PRIMER AÑO"), devuelve su texto."""
    original = (linea or "").strip()
    m = _ENCABEZADO_GRUPO_RE.match(sin_tildes(original))
    if not m:
        return None
    # Se devuelven las mismas palabras pero del renglón original, así el título
    # conserva las tildes y la Ñ.
    cuantas = len(m.group(0).split())
    return " ".join(original.split()[:cuantas]).strip(" .-")


def es_basura(linea):
    plano = sin_tildes(linea).lower()
    return any(palabra in plano for palabra in _BASURA)


def limpiar_renglon(linea):
    """Deja el nombre de la materia, o "" si el renglón no parece una materia."""
    texto = " ".join((linea or "").split())
    if not texto:
        return ""

    texto = _CODIGO_ADELANTE_RE.sub("", texto)

    # Correlativas al final: "... 12, 15" o "... (3) (7)"
    texto = re.sub(r'\s*\(\s*\d+(?:\s*[,y-]\s*\d+)*\s*\)\s*$', '', texto)

    tokens = texto.split()
    while tokens and _COLA_RE.match(tokens[-1].strip(",;.")):
        tokens.pop()
    texto = " ".join(tokens).strip(" .-|:;")

    if len(texto) < 4 or len(texto) > 90:
        return ""
    palabras = texto.split()
    if len(palabras) > MAX_PALABRAS:
        return ""
    if len(palabras) == 1 and sin_tildes(texto).upper() in _UNA_PALABRA_BASURA:
        return ""
    letras = sum(1 for c in texto if c.isalpha())
    if letras < 4 or letras < len(texto) * 0.6:
        return ""
    if not any(len(p) >= 3 for p in palabras if p.isalpha()):
        return ""
    return texto


def parsear_lineas(lineas):
    """De las líneas del PDF a (grupos, descartadas).

    grupos es [(titulo_del_grupo, [materias])]; descartadas son los renglones
    que se tiraron, para que el que revisa el borrador los mire.
    """
    grupos = [("", [])]
    descartadas = []
    vistas = set()

    for linea in lineas:
        texto = " ".join((linea or "").split())
        if not texto:
            continue

        grupo = es_encabezado_de_grupo(texto)
        if grupo:
            grupos.append((grupo.upper(), []))
            continue

        if es_basura(texto):
            descartadas.append(texto)
            continue

        materia = limpiar_renglon(texto)
        if not materia:
            descartadas.append(texto)
            continue

        clave = sin_tildes(materia).upper()
        if clave in vistas:
            continue
        vistas.add(clave)
        grupos[-1][1].append(materia)

    return [(t, m) for t, m in grupos if m], descartadas


# ---------------------------------------------------------------------------
# ARMADO DEL BORRADOR
# ---------------------------------------------------------------------------

def carrera_sugerida(nombre_archivo):
    """Del nombre del PDF a un nombre de carrera presentable.

    'Plan-de-estudios-Licenciatura-en-Quimica.pdf' -> 'Licenciatura en Quimica'
    """
    base = os.path.splitext(os.path.basename(nombre_archivo))[0]
    base = re.sub(r'[-_]+', ' ', base)
    base = re.sub(r'(?i)^\s*plan\s+de\s+estudios?\s*', '', base).strip()
    return " ".join(base.split())


def armar_borrador(grupos, descartadas, carrera, origen, desde_planilla=False):
    """El texto del .txt que se va a escribir."""
    total = sum(len(m) for _, m in grupos)
    if desde_planilla:
        cabecera = [
            "# BORRADOR generado desde la lista de materias de la planilla",
            "#     (Datos!AZ, la del desplegable de ASIGNATURAS)",
            "#",
            "# Los nombres son los mismos que usa el analítico, así que no hay",
            "# nada que emparejar. REVISALO igual:",
            "#",
            "# Qué mirar:",
            "#   1. Que la lista sea el plan completo y no le falte nada.",
            "#   2. ELECTIVAS: cuántas actividades electivas pide el plan, o",
            "#      ELECTIVAS_HS: cuántas horas, si las pide por carga horaria.",
            "#   3. Los años ([Primer año], etc.) los tenés que poner a mano:",
            "#      la planilla no los distingue. Es solo para el informe.",
        ]
    else:
        cabecera = [
            "# BORRADOR generado automáticamente desde:",
            "#     %s" % os.path.basename(origen),
            "#",
            "# REVISALO ANTES DE USARLO. La macro saca las materias del texto del",
            "# PDF, así que puede colarse algún renglón de más o faltar alguno.",
            "#",
            "# Qué mirar:",
            "#   1. La línea CARRERA: tiene que decir lo mismo que Datos!AZ3.",
            "#   2. Que estén todas las materias y ninguna de más.",
            "#   3. ELECTIVAS: cuántas actividades electivas pide el plan, o",
            "#      ELECTIVAS_HS: cuántas horas, si las pide por carga horaria.",
            "#   4. Al final están los renglones que descarté, por las dudas.",
        ]

    lineas = ["# " + "-" * 73] + cabecera + [
        "#",
        "# Se puede agregar a mano, en cualquier renglón:",
        "#   MATERIA | OTRO NOMBRE     nombres alternativos (como los escribe",
        "#                             el analítico)",
        "#   ? MATERIA                 optativa: si falta, no bloquea",
        "# " + "-" * 73,
        "",
        "CARRERA: %s" % carrera,
        "TITULO: %s" % carrera,
        "ELECTIVAS: 0",
        "",
    ]

    for titulo, materias in grupos:
        if titulo or not desde_planilla:
            lineas.append("[%s]" % (titulo or "Sin año"))
        lineas.extend(materias)
        lineas.append("")

    lineas += ["# " + "-" * 73, "# Materias detectadas: %d" % total]
    if descartadas:
        lineas += [
            "#",
            "# RENGLONES DESCARTADOS (revisá si alguno era una materia; para",
            "# recuperarlo, copialo arriba sin el # adelante):",
            "# " + "-" * 73,
        ]
        lineas += ["#   " + d for d in descartadas]
    lineas.append("")
    return "\n".join(lineas)


def nombre_de_archivo(carrera):
    """Nombre de archivo presentable para una carrera."""
    limpio = re.sub(r'[\\/:*?"<>|]+', " ", carrera or "PLAN")
    return " ".join(limpio.split()) + ".txt"


def carpeta_de_planes(carpeta_base, crear=True):
    """La carpeta de planes al lado del .ods. Si no está, la crea."""
    try:
        nombres = sorted(os.listdir(carpeta_base))
    except OSError:
        nombres = []
    for nombre in nombres:
        ruta = os.path.join(carpeta_base, nombre)
        if os.path.isdir(ruta) and sin_tildes(nombre).lower().startswith("planes"):
            return ruta
    ruta = os.path.join(carpeta_base, "Planes de estudio")
    if crear and not os.path.isdir(ruta):
        os.makedirs(ruta)
    return ruta


def guardar_plan_de_lista(carrera, materias, carpeta_destino):
    """Escribe el borrador de un plan sacado de la lista de la planilla."""
    texto = armar_borrador([("", materias)], [], carrera, "la planilla",
                           desde_planilla=True)
    destino = _sin_pisar(os.path.join(carpeta_destino, nombre_de_archivo(carrera)))
    with open(destino, "w", encoding="utf-8") as f:
        f.write(texto)
    return destino


# ---------------------------------------------------------------------------
# LECTURA DEL PDF
# ---------------------------------------------------------------------------

def lineas_del_pdf(ruta):
    """Devuelve (lineas, texto_crudo). Necesita pdfplumber."""
    import pdfplumber

    lineas, crudo = [], []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            crudo.append(texto)
            lineas.extend(texto.splitlines())
    return lineas, "\n".join(crudo)


def _sin_pisar(ruta):
    """Si el archivo ya existe, devuelve '<nombre> (nuevo).txt', '(nuevo 2)'..."""
    if not os.path.exists(ruta):
        return ruta
    base, ext = os.path.splitext(ruta)
    n = 1
    while True:
        candidato = "%s (nuevo%s)%s" % (base, "" if n == 1 else " %d" % n, ext)
        if not os.path.exists(candidato):
            return candidato
        n += 1


def importar(ruta_pdf, carrera=None):
    """Genera el borrador .txt al lado del PDF. Devuelve (ruta_txt, cantidad)."""
    lineas, crudo = lineas_del_pdf(ruta_pdf)
    grupos, descartadas = parsear_lineas(lineas)
    texto = armar_borrador(grupos, descartadas,
                           carrera or carrera_sugerida(ruta_pdf), ruta_pdf)

    destino = _sin_pisar(os.path.splitext(ruta_pdf)[0] + ".txt")
    with open(destino, "w", encoding="utf-8") as f:
        f.write(texto)

    with open(os.path.splitext(ruta_pdf)[0] + ".crudo.txt", "w", encoding="utf-8") as f:
        f.write(crudo)

    return destino, sum(len(m) for _, m in grupos)


# ---------------------------------------------------------------------------
# LIBREOFFICE (UNO)
# ---------------------------------------------------------------------------

def _msgbox(texto, titulo="Importar plan de estudios", tipo="INFOBOX"):
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


def _carpeta_del_ods(doc):
    try:
        import uno
        url = doc.getURL()
        if url:
            return os.path.dirname(uno.fileUrlToSystemPath(url))
    except Exception:
        pass
    return None


def ImportarPlanDeLaPlanilla(*args):
    """Botón / macro: arma el plan de la carrera elegida con la lista de la
    propia planilla (Datos!AZ, la del desplegable de ASIGNATURAS)."""
    doc = _documento_actual()
    if doc is None or not hasattr(doc, "getSheets"):
        _msgbox("Abrí el generador (.ods) y probá de nuevo.", tipo="ERRORBOX")
        return

    hojas = doc.getSheets()
    if not hojas.hasByName(HOJA_LISTA):
        _msgbox("No encontré la hoja '%s'." % HOJA_LISTA, tipo="ERRORBOX")
        return
    hoja = hojas.getByName(HOJA_LISTA)

    carrera = hoja.getCellByPosition(COL_LISTA, FILA_CARRERA).getString().strip()
    if not carrera:
        _msgbox("En Datos!AZ3 no hay ninguna carrera: elegila en el cuadro de "
                "carrera del EDITOR y volvé a probar.", tipo="WARNINGBOX")
        return

    celdas = [hoja.getCellByPosition(COL_LISTA, f).getString()
              for f in range(PRIMERA_FILA_LISTA, ULTIMA_FILA_LISTA)]
    materias = materias_de_la_lista(celdas)
    if not materias:
        _msgbox("La carrera '%s' no tiene cargada la lista de materias en la "
                "planilla (Datos!AZ está vacía o da #¡REF!).\n\n"
                "Para esta carrera usá ImportarPlanPDF, que la saca del PDF "
                "del plan." % carrera, tipo="WARNINGBOX")
        return

    base = _carpeta_del_ods(doc)
    if not base:
        _msgbox("Guardá el .ods antes de importar, así sé dónde dejar el plan.",
                tipo="WARNINGBOX")
        return

    try:
        destino = guardar_plan_de_lista(carrera, materias, carpeta_de_planes(base))
    except Exception as e:
        _msgbox("No pude guardar el plan:\n%s" % e, tipo="ERRORBOX")
        return

    _msgbox("Listo: %d materias de '%s'.\n\nQuedó en:\n%s\n\n"
            "Abrilo y revisalo: fijate que no falte ninguna materia y completá "
            "ELECTIVAS: (o ELECTIVAS_HS: si el plan las pide por horas)."
            % (len(materias), carrera, destino))


def ImportarPlanPDF(*args):
    """Botón / macro: elegí uno o varios PDF de planes y los pasa a .txt."""
    import uno

    ctx = uno.getComponentContext()
    picker = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.ui.dialogs.FilePicker", ctx)
    picker.setTitle("Elegir el PDF del plan de estudios")
    picker.appendFilter("Planes en PDF (*.pdf)", "*.pdf")
    try:
        picker.setMultiSelectionMode(True)
    except Exception:
        pass

    if picker.execute() != 1:
        return

    rutas = [uno.fileUrlToSystemPath(u) for u in (picker.getFiles() or [])]
    # Con multiselección, algunas versiones devuelven [carpeta, archivo1, ...]
    if len(rutas) > 1 and os.path.isdir(rutas[0]):
        rutas = [os.path.join(rutas[0], r) for r in rutas[1:]]
    if not rutas:
        return

    hechos, fallados = [], []
    for ruta in rutas:
        try:
            destino, cantidad = importar(ruta)
            hechos.append("   • %s  (%d materias)"
                          % (os.path.basename(destino), cantidad))
        except ImportError:
            _msgbox("Falta la librería pdfplumber, que es la misma que usa "
                    "ExtraerDatos para leer los PDF.", tipo="ERRORBOX")
            return
        except Exception as e:
            fallados.append("   • %s: %s" % (os.path.basename(ruta), e))

    texto = ""
    if hechos:
        texto += ("Listo. Se generaron estos borradores:\n%s\n\n"
                  "ABRILOS Y REVISALOS antes de usarlos: fijate sobre todo que "
                  "la línea CARRERA: diga lo mismo que Datos!AZ3, y que estén "
                  "todas las materias.\n" % "\n".join(hechos))
    if fallados:
        texto += "\nNo pude con:\n%s" % "\n".join(fallados)
    _msgbox(texto or "No se generó ningún borrador.",
            tipo="INFOBOX" if hechos and not fallados else "WARNINGBOX")


g_exportedScripts = (ImportarPlanDeLaPlanilla, ImportarPlanPDF)


# ---------------------------------------------------------------------------
# MODO TERMINAL
# ---------------------------------------------------------------------------

def _importar_de_planilla_en_terminal(ruta_ods):
    """Modo terminal del import desde la planilla (usa el lector de ChequearPlan)."""
    import ChequearPlan

    hojas = ChequearPlan._grillas_de_ods(ruta_ods)
    grilla = hojas.get(HOJA_LISTA) or []

    def celda(fila, col):
        if fila < len(grilla) and col < len(grilla[fila]):
            return grilla[fila][col] or ""
        return ""

    carrera = celda(FILA_CARRERA, COL_LISTA).strip()
    materias = materias_de_la_lista(
        [celda(f, COL_LISTA) for f in range(PRIMERA_FILA_LISTA, ULTIMA_FILA_LISTA)])
    if not carrera or not materias:
        print("No encontré la carrera o su lista de materias en %s "
              "(Datos!AZ3 y Datos!AZ5 en adelante)." % ruta_ods)
        return 1

    destino = guardar_plan_de_lista(
        carrera, materias, carpeta_de_planes(os.path.dirname(os.path.abspath(ruta_ods))))
    print("%s -> %s (%d materias)" % (carrera, destino, len(materias)))
    return 0


def main(argv):
    if len(argv) < 2:
        print("Uso: python3 ImportarPlan.py plan.pdf [otro.pdf ...]")
        print("     python3 ImportarPlan.py --planilla GENERADOR.ods")
        return 2

    if argv[1] in ("--planilla", "-p"):
        if len(argv) < 3:
            print("Falta el .ods: python3 ImportarPlan.py --planilla GENERADOR.ods")
            return 2
        return _importar_de_planilla_en_terminal(argv[2])

    for ruta in argv[1:]:
        try:
            destino, cantidad = importar(ruta)
            print("%s -> %s (%d materias)"
                  % (os.path.basename(ruta), os.path.basename(destino), cantidad))
        except Exception as e:
            print("%s: ERROR %s" % (os.path.basename(ruta), e))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
