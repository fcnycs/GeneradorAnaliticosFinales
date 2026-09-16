"""Pruebas de la lógica de ChequearPlan.py (no necesita LibreOffice).

    python3 pruebas_ChequearPlan.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ChequearPlan as C

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

print("Fallas: %d" % len(errores))
for e in errores:
    print("  -", e)
sys.exit(1 if errores else 0)
