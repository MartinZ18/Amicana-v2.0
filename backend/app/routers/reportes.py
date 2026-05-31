"""Reportes simples para el panel admin.

Solo conteos y listados básicos a partir de datos reales de la BD.
Sin IA ni análisis complejos.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..database import get_connection
from ..dependencies import require_rol
from ..utils.responses import error, ok

router = APIRouter(tags=["reportes"])

_STAFF = ("admin", "administrativo")
_ESTADOS_DEUDORES = {"vencida", "pendiente", "pendiente_verificacion", "todas"}


@router.get("/reportes/resumen")
def resumen(user: dict = Depends(require_rol(*_STAFF))):
    """Métricas y listados rápidos del estado del instituto."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("UPDATE cuotas SET estado='vencida' "
                       "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
        conn.commit()

        cursor.execute("SELECT COUNT(*) AS total FROM usuarios WHERE rol='alumno'")
        total_alumnos = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(DISTINCT alumno_id) AS total "
            "FROM cuotas WHERE estado='vencida'"
        )
        alumnos_con_deuda = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(monto), 0) AS monto "
            "FROM cuotas WHERE estado='vencida'"
        )
        cuotas_vencidas_row = cursor.fetchone()

        cursor.execute(
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.creado_en, "
            "       c.nombre AS curso "
            "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
            "WHERE u.rol='alumno' "
            "ORDER BY u.creado_en DESC LIMIT 10"
        )
        ultimos = cursor.fetchall()

        cursor.execute(
            "SELECT c.id, c.nombre, COUNT(u.id) AS alumnos "
            "FROM cursos c LEFT JOIN usuarios u "
            "       ON u.curso_id = c.id AND u.rol='alumno' "
            "WHERE c.activo=1 "
            "GROUP BY c.id, c.nombre ORDER BY alumnos DESC"
        )
        por_curso = cursor.fetchall()
    finally:
        conn.close()

    for u in ultimos:
        u["creado_en"] = str(u["creado_en"]) if u.get("creado_en") else None

    return ok(data={
        "alumnos_totales": total_alumnos,
        "alumnos_con_deuda": alumnos_con_deuda,
        "cuotas_vencidas": {
            "cantidad": cuotas_vencidas_row["total"],
            "monto":    float(cuotas_vencidas_row["monto"] or 0),
        },
        "ultimos_alumnos": ultimos,
        "alumnos_por_curso": por_curso,
    })


@router.get("/reportes/deudores")
def deudores(
    estado: Optional[str] = Query(default="vencida"),
    user: dict = Depends(require_rol(*_STAFF)),
):
    """Lista alumnos con cuotas en el estado indicado.

    `estado` admite: vencida (default), pendiente, pendiente_verificacion, todas.
    `todas` agrupa los tres estados que generan deuda.
    """
    estado = (estado or "vencida").lower()
    if estado not in _ESTADOS_DEUDORES:
        raise error("estado inválido", 400)

    if estado == "todas":
        filtro_estado = "estado IN ('vencida','pendiente','pendiente_verificacion')"
    else:
        filtro_estado = "estado = %s"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("UPDATE cuotas SET estado='vencida' "
                       "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
        conn.commit()

        sql = (
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, "
            "       c.nombre AS curso, "
            "       COUNT(cu.id) AS cuotas_adeudadas, "
            "       COALESCE(SUM(cu.monto), 0) AS deuda_total "
            "FROM usuarios u "
            "LEFT JOIN cursos c ON u.curso_id = c.id "
            "JOIN cuotas cu ON cu.alumno_id = u.id "
            f"WHERE u.rol='alumno' AND cu.{filtro_estado} "
            "GROUP BY u.id, u.nombre, u.apellido, u.email, u.dni, c.nombre "
            "ORDER BY deuda_total DESC, u.apellido, u.nombre"
        )
        params = () if estado == "todas" else (estado,)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    finally:
        conn.close()

    deudores = []
    for r in rows:
        deudores.append({
            "id": r["id"],
            "nombre": r["nombre"],
            "apellido": r.get("apellido"),
            "email": r["email"],
            "dni": r.get("dni"),
            "curso": r.get("curso"),
            "cuotas_adeudadas": r["cuotas_adeudadas"],
            "deuda_total": float(r["deuda_total"] or 0),
        })

    return ok(data={"estado": estado, "total": len(deudores), "deudores": deudores})


@router.get("/reportes/cuotas-vencidas")
def cuotas_vencidas(user: dict = Depends(require_rol(*_STAFF))):
    """Listado detallado de cuotas vencidas (una fila por cuota)."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("UPDATE cuotas SET estado='vencida' "
                       "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
        conn.commit()

        cursor.execute(
            "SELECT cu.id, cu.concepto, cu.monto, cu.fecha_vencimiento, "
            "       u.id AS alumno_id, u.nombre, u.apellido, u.email, u.dni, "
            "       c.nombre AS curso, "
            "       DATEDIFF(CURDATE(), cu.fecha_vencimiento) AS dias_vencida "
            "FROM cuotas cu "
            "JOIN usuarios u ON u.id = cu.alumno_id "
            "LEFT JOIN cursos c ON u.curso_id = c.id "
            "WHERE cu.estado='vencida' "
            "ORDER BY cu.fecha_vencimiento ASC"
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    cuotas = []
    for r in rows:
        cuotas.append({
            "cuota_id": r["id"],
            "concepto": r["concepto"],
            "monto": float(r["monto"]),
            "fecha_vencimiento": str(r["fecha_vencimiento"]),
            "dias_vencida": int(r["dias_vencida"] or 0),
            "alumno_id": r["alumno_id"],
            "nombre": r["nombre"],
            "apellido": r.get("apellido"),
            "email": r["email"],
            "dni": r.get("dni"),
            "curso": r.get("curso"),
        })

    return ok(data={"total": len(cuotas), "cuotas": cuotas})
