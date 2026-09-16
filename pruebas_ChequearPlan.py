"""Pruebas de ChequearPlan.py e ImportarPlan.py (no necesitan LibreOffice).

    python3 pruebas_ChequearPlan.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ChequearPlan as C
import ImportarPlan as I

PLAN_EJEMPLO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "Planes de estudio",
                            "EJEMPLO - TECNICATURA EN ENFERMERIA.txt")

errores = []
def chk(cond, msg):
    if not cond:
        errores.append(msg)

# --- normalizacion ---
chk(C.normalizar("1A - Anatomía y Fisiología II") == "ANATOMIA Y FISIOLOGIA 2", C.normalizar("1A - Anatomía y Fisiología II"))
chk(C.normalizar("ETICA - DEONTOLOGIA") == "ETICA DEONTOLOGIA", C.normalizar("ETICA - DEONTOLOGIA"))
chk(C.normalizar("MED-2 - Farmacología") == "FARMACOLOGIA", C.normalizar("MED-2 - Farmacología"))
chk(C.normalizar("Enseñanza") == "ENSENANZA", C.normalizar("Enseñanza"))
chk(C.normalizar("") == "", "vacío")

# --- notas ---
casos = {
    "7 (SIETE)": C.APROBADA, "SIETE (7)": C.APROBADA, "4": C.APROBADA,
    "3 (TRES)": C.DESAPROBADA, "TRES (3)": C.DESAPROBADA,
    "Ausente": C.DESAPROBADA, "AUSENTE": C.DESAPROBADA,
    "Aprobado": C.APROBADA,
    "APROBADO POR RESOLUCION DFCNyCS 461/17": C.APROBADA,
    "Aprobado por Equivalencia": C.APROBADA,
    "": C.REVISAR, "   ": C.REVISAR, "s/d": C.REVISAR,
    "10 (DIEZ)": C.APROBADA, "0 (CERO)": C.DESAPROBADA,
}
for nota, esperado in casos.items():
    real = C.estado_de_la_nota(nota)
    chk(real == esperado, "nota %r -> %s (esperaba %s)" % (nota, real, esperado))

# --- una materia rendida dos veces: vale la aprobada ---
plan = {"titulo": "X", "electivas": 0, "ruta": "",
        "materias": [C.MateriaPlan("FARMACOLOGIA", orden=0)]}
cursadas = C.armar_cursadas([("FARMACOLOGIA", "2 (DOS)"), ("FARMACOLOGIA", "8 (OCHO)")])
r = C.comparar(plan, cursadas)
chk(r["ok"] and len(r["aprobadas"]) == 1 and not r["pendientes"], "repetida: %s" % r["ok"])
chk(len(r["fuera_del_plan"]) == 1, "la otra queda como fuera del plan")

# --- plan vacío no explota ---
r = C.comparar({"titulo": "X", "electivas": 0, "materias": []}, C.armar_cursadas([("A", "7")]))
chk(r["ok"], "plan vacío")

# --- electivas ---
plan = {"titulo": "X", "electivas": 2, "materias": []}
r = C.comparar(plan, C.armar_cursadas([("ACTIVIDAD ELECTIVA: TALLER", "7"),
                                       ("Actividad Electiva - Inglés", "Aprobado")]))
chk(r["electivas"]["tiene"] == 2 and r["ok"], "electivas: %s" % r["electivas"])
r = C.comparar(plan, C.armar_cursadas([("ACTIVIDAD ELECTIVA: TALLER", "2 (DOS)")]))
chk(r["faltan_electivas"] == 2 and not r["ok"], "electiva desaprobada no cuenta")

# --- dos materias parecidas no se pisan ---
plan = {"titulo": "X", "electivas": 0, "materias": [
    C.MateriaPlan("ENFERMERIA MEDICA", orden=0), C.MateriaPlan("ENFERMERIA QUIRURGICA", orden=1)]}
r = C.comparar(plan, C.armar_cursadas([("ENFERMERIA QUIRURGICA", "7"), ("ENFERMERIA MEDICA", "7")]))
chk(len(r["aprobadas"]) == 2 and not r["aproximadas"], "parecidas: %s" % [(m.nombre, c["nombre"]) for m, c, _ in r["aprobadas"]])

# --- alias y optativas desde archivo ---
p = C.leer_plan(PLAN_EJEMPLO)
chk(len(p["materias"]) == 15, "materias leidas: %d" % len(p["materias"]))
chk(p["electivas"] == 2, "electivas del plan")
chk(p["titulo"].startswith("Tecnicatura"), "titulo")
chk(sum(1 for m in p["materias"] if not m.obligatoria) == 1, "una optativa")
chk(p["materias"][0].alias == ["ANATOMOFISIOLOGIA", "ANATOMIA Y FISIOLOGIA HUMANA"], p["materias"][0].alias)

# --- detalle: una fila por materia + extras ---
filas = C.armar_detalle(C.comparar(p, C.armar_cursadas([("PARASITOLOGIA", "7"), ("OTRA COSA", "7")])))
chk(filas[0] == C.ENCABEZADO_INFORME, "encabezado")
chk(len(filas) == 1 + 15 + 2 + 1, "filas del detalle: %d" % len(filas))
chk(all(len(f) == len(C.ENCABEZADO_INFORME) for f in filas), "ancho parejo de filas")

# --- CARRERA: encuentra el plan sin importar el nombre del archivo ---------
import tempfile
carpeta = tempfile.mkdtemp()
with open(os.path.join(carpeta, "TUQ.txt"), "w", encoding="utf-8") as f:
    f.write("CARRERA: Tecnicatura Universitaria en Química\n"
            "CARRERA: TUQ\n"
            "MATEMATICA I   # nota al final del renglón\n")
ruta, exactitud = C.buscar_plan_de_carrera("TECNICATURA UNIVERSITARIA EN QUIMICA", [carpeta])
chk(ruta is not None and exactitud == 1.0, "plan por CARRERA: %s" % ruta)
ruta, _ = C.buscar_plan_de_carrera("TUQ", [carpeta])
chk(ruta is not None, "plan por sigla")
p = C.leer_plan(os.path.join(carpeta, "TUQ.txt"))
chk(p["carreras"] == ["Tecnicatura Universitaria en Química", "TUQ"], p["carreras"])
chk(len(p["materias"]) == 1 and p["materias"][0].nombre == "MATEMATICA I",
    "comentario al final: %s" % [m.nombre for m in p["materias"]])
chk(p["titulo"] == "Tecnicatura Universitaria en Química", "titulo por defecto")

# --- importador: renglones tipicos de un plan en PDF ----------------------
chk(I.limpiar_renglon("1 ANATOMÍA Y FISIOLOGÍA 1º Cuatr. 6 hs. sem. -") == "ANATOMÍA Y FISIOLOGÍA", "horas y regimen")
chk(I.limpiar_renglon("Q3 QUÍMICA BIOLÓGICA 2°C 96 hs 5, 6") == "QUÍMICA BIOLÓGICA", "codigo y correlativas")
chk(I.limpiar_renglon("12) Práctica Profesional Supervisada 200 hs") == "Práctica Profesional Supervisada", "PPS es materia")
chk(I.limpiar_renglon("TOTAL 2800") == "", "total no es materia")
chk(I.limpiar_renglon("Res. C.S. 461/17") == "", "resolucion no es materia")
chk(I.es_basura("El alumno deberá acreditar un idioma extranjero"), "requisito no es materia")
chk(I.es_encabezado_de_grupo("PRIMER AÑO") == "PRIMER AÑO", "encabezado conserva la Ñ")
chk(I.es_encabezado_de_grupo("QUÍMICA I") is None, "una materia no es encabezado")
chk(I.carrera_sugerida("Plan-de-estudios-Licenciatura-en-Quimica.pdf") == "Licenciatura en Quimica",
    I.carrera_sugerida("Plan-de-estudios-Licenciatura-en-Quimica.pdf"))

# --- el borrador que genera el importador lo tiene que poder leer el chequeo ---
lineas = """UNIVERSIDAD NACIONAL DE LA PATAGONIA
PLAN DE ESTUDIOS - LICENCIATURA EN QUÍMICA
Código Asignatura Régimen Carga horaria Correlativas
PRIMER AÑO
1 MATEMÁTICA I Anual 128 hs -
2 QUÍMICA GENERAL E INORGÁNICA Anual 160 hs -
SEGUNDO AÑO
3 QUÍMICA ORGÁNICA I 2°C 128 hs (2)
Página 1 de 4""".splitlines()
grupos, descartadas = I.parsear_lineas(lineas)
chk([t for t, _ in grupos] == ["PRIMER AÑO", "SEGUNDO AÑO"], [t for t, _ in grupos])
chk(sum(len(m) for _, m in grupos) == 3, "materias detectadas")
borrador = I.armar_borrador(grupos, descartadas, "Licenciatura en Química", "x.pdf")
destino = os.path.join(carpeta, "borrador.txt")
with open(destino, "w", encoding="utf-8") as f:
    f.write(borrador)
p = C.leer_plan(destino)
chk([m.nombre for m in p["materias"]] == ["MATEMÁTICA I", "QUÍMICA GENERAL E INORGÁNICA", "QUÍMICA ORGÁNICA I"],
    [m.nombre for m in p["materias"]])
chk(p["carreras"] == ["Licenciatura en Química"], "CARRERA en el borrador")
chk(p["materias"][0].grupo == "PRIMER AÑO", "grupo del borrador")
r = C.comparar(p, C.armar_cursadas([("MATEMATICA I", "7 (SIETE)"),
                                    ("QUIMICA GENERAL E INORGANICA", "8"),
                                    ("QUIMICA ORGANICA I", "Aprobado")]))
chk(r["ok"] and not r["aproximadas"], "el borrador sirve para chequear: %s" % r["faltantes"])


# --- la lista de materias que ya tiene la planilla (Datos!AZ) --------------
celdas = ["SELECCIÓN", "", "ACTIVIDAD ELECTIVA: ESCRIBIR SU NOMBRE Y LAS HORAS",
          "ENFERMERIA BASICA", "CIENCIAS BIOLOGICAS", "ENFERMERIA BASICA",
          "#¡REF!", "PRACTICA INTEGRADA I", "0", "0", "0"]
chk(I.materias_de_la_lista(celdas) == ["ENFERMERIA BASICA", "CIENCIAS BIOLOGICAS",
                                       "PRACTICA INTEGRADA I"],
    I.materias_de_la_lista(celdas))
chk(I.materias_de_la_lista(["0", "0", ""]) == [], "lista vacía o rota")
chk(I.nombre_de_archivo("GEOLOGIA (PLAN 2018)") == "GEOLOGIA (PLAN 2018).txt",
    I.nombre_de_archivo("GEOLOGIA (PLAN 2018)"))

# --- electivas por carga horaria ------------------------------------------
chk(C.horas_de("95 hs") == 95 and C.horas_de("4,5") == 4.5 and C.horas_de("") == 0,
    "horas_de")
filas_editor = [("ENFERMERIA BASICA", "170"),
                ("ACTIVIDAD ELECTIVA: TALLER DE RCP", "60"),
                ("ACTIVIDAD ELECTIVA: INFORMATICA", "35")]
chk(C.sumar_horas_electivas(filas_editor) == (95.0, 2), C.sumar_horas_electivas(filas_editor))

plan_hs = {"titulo": "X", "electivas": 0, "electivas_hs": 95, "materias": []}
cursadas_hs = C.armar_cursadas([("ACTIVIDAD ELECTIVA: TALLER DE RCP", "8")])
chk(C.comparar(plan_hs, cursadas_hs, 95.0)["ok"], "95 de 95 hs")
r = C.comparar(plan_hs, cursadas_hs, 60.0)
chk(not r["ok"] and r["faltan_horas_electivas"] == 35, "faltan 35 hs")
# si no se pudieron leer las horas, se avisa pero no se da por faltante
r = C.comparar(plan_hs, cursadas_hs, None)
chk(r["ok"] and r["horas_electivas_sin_leer"], "horas sin leer: avisa, no bloquea")
chk("no pude leer la columna Hs" in C.armar_resumen("X", r), C.armar_resumen("X", r))

# --- el plan real de ENFERMERIA -------------------------------------------
enf = C.leer_plan(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "Planes de estudio", "ENFERMERIA.txt"))
chk(len(enf["materias"]) == 19, "materias de enfermería: %d" % len(enf["materias"]))
chk(enf["electivas_hs"] == 95 and enf["carreras"] == ["ENFERMERIA"], "cabecera de enfermería")
del_analitico = [
    "ENFERMERIA BASICA", "CIENCIAS BIOLOGICAS", "ANTROPOLOGIA", "SOCIOLOGIA I",
    "FILOSOFIA I", "ENFERMERIA COMUNITARIA I", "MICROBIOLOGIA Y PARASITOLOGIA",
    "ENFERMERIA DEL ADULTO Y EL ANCIANO", "ENFERMERIA MATERNO - INFANTIL",
    "NUTRICION Y DIETOTERAPIA", "EPIDEMIOLOGIA", "FARMACOLOGIA", "PSICOLOGIA",
    "ETICA Y DEONTOLOGIA PROFESIONAL I", "ENFERMERIA DEL NIÑO Y EL ADOLESCENTE",
    "ENFERMERIA EN SALUD MENTAL", "INVESTIGACION EN ENFERMERIA I",
    "GESTION DE LOS SERVICIOS DE ENFERMERIA HOSPITALARIOS Y COMUNITARIOS I",
    "PRACTICA INTEGRADA I",
]
r = C.comparar(enf, C.armar_cursadas([(m, "7 (SIETE)") for m in del_analitico]), 95.0)
chk(r["ok"] and not r["aproximadas"] and len(r["aprobadas"]) == 19,
    "enfermería completa: faltan %s" % [m.nombre for m in r["faltantes"]])
# el analítico a veces escribe el guion distinto o con tildes: da igual
r = C.comparar(enf, C.armar_cursadas(
    [(m, "7") for m in del_analitico[:8]] +
    [("ENFERMERÍA MATERNO-INFANTIL", "7")] +
    [(m, "7") for m in del_analitico[9:]]), 95.0)
chk(r["ok"] and not r["aproximadas"], "materno-infantil con guion pegado")


print("Fallas: %d" % len(errores))
for e in errores:
    print("  -", e)
sys.exit(1 if errores else 0)
