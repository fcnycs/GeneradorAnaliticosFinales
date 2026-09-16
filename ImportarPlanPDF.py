# -*- coding: utf-8 -*-
"""
Importar un plan de estudios desde el PDF oficial
=================================================
Toma el PDF del plan y escribe al lado un borrador .txt con las materias, en el
formato que lee ChequearPlan.py.

Es un BORRADOR: hay que abrirlo y revisarlo una vez (sacar lo que sobra, agregar
lo que falte, poner la línea CARRERA: como figura en Datos!AZ3). Después ya
queda hecho para siempre, salvo que cambie el plan.

Junto al .txt deja también un "<nombre>.crudo.txt" con todo el texto del PDF tal
cual, para copiar y pegar de ahí si el borrador salió flojo.

Se puede usar de dos formas:
  1) Desde LibreOffice (botón o Herramientas > Macros)  ->  ImportarPlanPDF()
  2) Desde la terminal                                  ->  python3 ImportarPlanPDF.py plan.pdf [otro.pdf ...]
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
# RECONOCER LOS RENGLONES DEL PLAN
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


def armar_borrador(grupos, descartadas, carrera, origen):
    """El texto del .txt que se va a escribir."""
    total = sum(len(m) for _, m in grupos)
    lineas = [
        "# " + "-" * 73,
        "# BORRADOR generado automáticamente desde:",
        "#     %s" % os.path.basename(origen),
        "#",
        "# REVISALO ANTES DE USARLO. La macro saca las materias del texto del",
        "# PDF, así que puede colarse algún renglón de más o faltar alguno.",
        "#",
        "# Qué mirar:",
        "#   1. La línea CARRERA: tiene que decir lo mismo que Datos!AZ3.",
        "#   2. Que estén todas las materias y ninguna de más.",
        "#   3. ELECTIVAS: cuántas actividades electivas pide el plan.",
        "#   4. Al final están los renglones que descarté, por las dudas.",
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
        lineas.append("[%s]" % (titulo or "Sin año"))
        lineas.extend(materias)
        lineas.append("")

    lineas += [
        "# " + "-" * 73,
        "# Materias detectadas: %d" % total,
        "#",
        "# RENGLONES DESCARTADOS (revisá si alguno era una materia; para",
        "# recuperarlo, copialo arriba sin el # adelante):",
        "# " + "-" * 73,
    ]
    lineas += ["#   " + d for d in descartadas]
    lineas.append("")
    return "\n".join(lineas)


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


g_exportedScripts = (ImportarPlanPDF,)


# ---------------------------------------------------------------------------
# MODO TERMINAL
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print("Uso: python3 ImportarPlanPDF.py plan.pdf [otro.pdf ...]")
        return 2
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
