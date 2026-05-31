"""Endpoints de datos para el chatbot Ianna.

Salvo /chatbot/faq (público), todos requieren autenticación inter-servicio
vía la cabecera `X-Chatbot-Key` (manejada por get_chatbot_or_current_user).
El alumno se identifica por email o DNI dentro del body / path.

Separado de routers/chatbot.py (que persiste sesiones) para mantener
la responsabilidad acotada.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from ..auth import get_chatbot_or_current_user, is_chatbot
from ..database import get_connection
from ..utils.responses import error, ok

router = APIRouter(prefix="/chatbot", tags=["chatbot-data"])


def _solo_chatbot(user: dict) -> None:
    if not is_chatbot(user):
        raise error("Solo el chatbot puede consumir este endpoint", 403)


class IdentificarReq(BaseModel):
    email: Optional[EmailStr] = None
    dni:   Optional[str]      = Field(default=None, pattern=r"^\d{7,8}$")


@router.post("/identificar-alumno")
def identificar_alumno(data: IdentificarReq,
                       user: dict = Depends(get_chatbot_or_current_user)):
    """Resuelve un alumno por email o DNI. Devuelve datos básicos + curso."""
    _solo_chatbot(user)
    if not data.email and not data.dni:
        raise error("Indicá email o DNI", 400)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        base = (
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.telefono, "
            "       u.curso_id, u.modalidad, "
            "       c.nombre AS curso, c.modalidad AS modalidad_curso "
            "FROM usuarios u LEFT JOIN cursos c ON c.id=u.curso_id "
        )
        if data.email:
            cursor.execute(base + "WHERE u.email=%s AND u.rol='alumno'", (str(data.email),))
        else:
            cursor.execute(base + "WHERE u.dni=%s AND u.rol='alumno'", (data.dni,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        raise error("Alumno no encontrado", 404)
    return ok(data={"alumno": row})


@router.get("/alumno/{alumno_id}/estado-cuotas")
def estado_cuotas_alumno(alumno_id: int,
                         user: dict = Depends(get_chatbot_or_current_user)):
    """Resumen de cuotas: pendientes, vencidas, pagadas, deuda y `apto_examen`."""
    _solo_chatbot(user)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("UPDATE cuotas SET estado='vencida' "
                       "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
        conn.commit()

        cursor.execute(
            "SELECT estado, COUNT(*) AS n, COALESCE(SUM(monto), 0) AS total "
            "FROM cuotas WHERE alumno_id=%s GROUP BY estado",
            (alumno_id,),
        )
        rows = cursor.fetchall()

        cursor.execute(
            "SELECT id, concepto, monto, fecha_vencimiento, estado "
            "FROM cuotas WHERE alumno_id=%s AND estado IN ('vencida','pendiente') "
            "ORDER BY fecha_vencimiento ASC",
            (alumno_id,),
        )
        detalle = cursor.fetchall()
    finally:
        conn.close()

    resumen = {
        r["estado"]: {"cantidad": r["n"], "total": float(r["total"])}
        for r in rows
    }
    deuda_total = sum(
        v["total"] for k, v in resumen.items()
        if k in ("vencida", "pendiente", "pendiente_verificacion")
    )
    cuotas_vencidas = (resumen.get("vencida") or {}).get("cantidad", 0)
    apto_examen = cuotas_vencidas == 0

    for c in detalle:
        c["monto"] = float(c["monto"])
        c["fecha_vencimiento"] = str(c["fecha_vencimiento"])

    return ok(data={
        "resumen":         resumen,
        "deuda_total":     float(deuda_total),
        "cuotas_vencidas": cuotas_vencidas,
        "apto_examen":     apto_examen,
        "detalle":         detalle,
    })


@router.get("/alumno/{alumno_id}/aptitud-examen")
def aptitud_examen(alumno_id: int,
                   user: dict = Depends(get_chatbot_or_current_user)):
    """Aptitud para exámenes internacionales.

    Combina: nivel actual del alumno (progreso_alumno → niveles.codigo),
    promedio general (notas_alumno) y cuotas vencidas. Devuelve por examen
    si está apto y con qué condiciones.
    """
    _solo_chatbot(user)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT u.id, u.nombre, u.apellido, c.nombre AS curso, c.categoria, "
            "       n.codigo AS nivel "
            "FROM usuarios u "
            "LEFT JOIN cursos c ON c.id=u.curso_id "
            "LEFT JOIN progreso_alumno pa ON pa.alumno_id=u.id "
            "LEFT JOIN niveles n ON n.id=pa.nivel_id "
            "WHERE u.id=%s AND u.rol='alumno'",
            (alumno_id,),
        )
        info = cursor.fetchone()
        if not info:
            raise error("Alumno no encontrado", 404)

        cursor.execute(
            "SELECT seccion, AVG(nota) AS prom, COUNT(*) AS n "
            "FROM notas_alumno WHERE alumno_id=%s GROUP BY seccion",
            (alumno_id,),
        )
        secs = {
            r["seccion"]: {"prom": float(r["prom"]), "n": r["n"]}
            for r in cursor.fetchall()
        }

        cursor.execute(
            "SELECT AVG(nota) AS prom, COUNT(*) AS n FROM notas_alumno WHERE alumno_id=%s",
            (alumno_id,),
        )
        gen = cursor.fetchone() or {}
        promedio = float(gen.get("prom") or 0)
        total    = int(gen.get("n") or 0)

        cursor.execute(
            "SELECT COUNT(*) AS n FROM cuotas "
            "WHERE alumno_id=%s AND estado='vencida'",
            (alumno_id,),
        )
        vencidas = (cursor.fetchone() or {}).get("n", 0)
    finally:
        conn.close()

    nivel = info.get("nivel")
    orden_nivel = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    nivel_actual = orden_nivel.get(nivel or "", 0)

    examenes: list[dict] = []

    def _add(nombre: str, requiere_nivel: str, prom_min: float) -> None:
        nivel_req = orden_nivel.get(requiere_nivel, 0)
        cumple = (
            vencidas == 0
            and (total == 0 or promedio >= prom_min)
            and nivel_actual >= nivel_req
        )
        examenes.append({
            "examen":          nombre,
            "requiere_nivel":  requiere_nivel,
            "promedio_minimo": prom_min,
            "apto":            cumple,
        })

    _add("TOEIC Bridge", "A2", 6.0)
    _add("ECECE",        "A2", 7.0)
    _add("TOEIC",        "B1", 7.0)
    _add("TOEFL iBT",    "B2", 8.0)

    return ok(data={
        "alumno":             info,
        "promedio_general":   round(promedio, 2),
        "total_notas":        total,
        "promedio_secciones": secs,
        "cuotas_vencidas":    vencidas,
        "examenes":           examenes,
    })


@router.get("/cursos/info")
def info_cursos(user: dict = Depends(get_chatbot_or_current_user)):
    """Cursos activos para asesorar a alumnos potenciales (modalidad+categoría)."""
    _solo_chatbot(user)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, nombre, descripcion, monto_cuota, modalidad, categoria, activo "
            "FROM cursos WHERE activo=1 ORDER BY categoria, nombre"
        )
        cursos = cursor.fetchall()
    finally:
        conn.close()
    for c in cursos:
        c["monto_cuota"] = float(c["monto_cuota"])
    return ok(data={"cursos": cursos})


@router.get("/welcome")
def welcome():
    """Mensaje de bienvenida configurable (público, sin auth)."""
    return ok(data={
        "texto": (
            "Hola, soy Ianna, la asistente virtual de AMICANA.\n"
            "Puedo ayudarte con:\n"
            "  - Consultar el estado de tus cuotas\n"
            "  - Pagar una cuota\n"
            "  - Información sobre cursos y modalidades\n"
            "  - Asesorarte sobre exámenes internacionales (ECECE, TOEIC, TOEFL)\n"
            "¿En qué te puedo ayudar?"
        ),
        "capacidades": [
            "estado de cuotas",
            "pago de cuotas",
            "información de cursos",
            "aptitud para exámenes internacionales",
        ],
    })


@router.get("/faq")
def faq_publico():
    """FAQ público (sin auth) para preguntas frecuentes desde el widget."""
    return ok(data={"faq": [
        {"q": "¿Cuáles son los horarios del instituto?",
         "a": "Atendemos de lunes a viernes de 8:30 a 21:00 y sábados de 8:30 a 12:30."},
        {"q": "¿Cómo me inscribo?",
         "a": "Podés acercarte a la sede o solicitar asesoramiento por este chat indicándonos "
              "el nivel y modalidad que te interesa."},
        {"q": "¿Qué modalidades ofrecen?",
         "a": "Presencial, virtual e híbrida. Cada curso indica su modalidad disponible."},
        {"q": "¿Qué exámenes internacionales puedo rendir?",
         "a": "ECECE (a partir de A2), TOEIC Bridge (A2), TOEIC (B1) y TOEFL iBT (B2). "
              "El asistente puede revisar tu progreso para sugerirte cuáles."},
        {"q": "¿Cómo pago la cuota?",
         "a": "Por MercadoPago o generando un código QR para pago en efectivo desde tu "
              "panel de Mis Cuotas."},
    ]})
