"""Comunicados internos del staff (no visibles al alumno).

Solo admin/administrativo pueden listar, crear y eliminar comunicados.
Si un alumno intenta acceder a `/comunicados` recibe 403.
"""
from fastapi import APIRouter, Depends

from ..database import get_connection
from ..dependencies import require_rol
from ..schemas.comunicados import ComunicadoCreate
from ..utils.responses import error, ok

router = APIRouter(tags=["comunicados"])

_STAFF = ("admin", "administrativo")


def _serializar(row: dict) -> dict:
    return {
        "id": row["id"],
        "asunto": row["asunto"],
        "cuerpo": row["cuerpo"],
        "destinatarios": row["destinatarios"],
        "curso_id": row.get("curso_id"),
        "curso": row.get("curso"),
        "creado_por": row["creado_por"],
        "creado_por_nombre": row.get("creado_por_nombre"),
        "fecha": str(row["fecha"]) if row.get("fecha") else None,
    }


@router.get("/comunicados")
def listar_comunicados(user: dict = Depends(require_rol(*_STAFF)),
                       limite: int = 50):
    """Lista los últimos comunicados (solo staff)."""
    if limite < 1 or limite > 200:
        limite = 50
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT cm.id, cm.asunto, cm.cuerpo, cm.destinatarios, "
            "       cm.curso_id, cm.creado_por, cm.fecha, "
            "       c.nombre AS curso, "
            "       TRIM(CONCAT(IFNULL(u.nombre,''), ' ', IFNULL(u.apellido,''))) AS creado_por_nombre "
            "FROM comunicados cm "
            "LEFT JOIN cursos c    ON cm.curso_id   = c.id "
            "LEFT JOIN usuarios u  ON cm.creado_por = u.id "
            "ORDER BY cm.fecha DESC LIMIT %s",
            (limite,),
        )
        rows = [_serializar(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return ok(data={"comunicados": rows, "total": len(rows)})


@router.post("/comunicados")
def crear_comunicado(data: ComunicadoCreate,
                     user: dict = Depends(require_rol(*_STAFF))):
    """Crea un comunicado interno."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if data.curso_id is not None:
            cursor.execute("SELECT id FROM cursos WHERE id=%s", (data.curso_id,))
            if not cursor.fetchone():
                raise error("Curso inexistente", 400)
        cursor.execute(
            "INSERT INTO comunicados (asunto, cuerpo, destinatarios, curso_id, creado_por) "
            "VALUES (%s, %s, %s, %s, %s)",
            (data.asunto, data.cuerpo, data.destinatarios,
             data.curso_id, user.get("id")),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    return ok(data={"id": new_id}, mensaje="Comunicado registrado")


@router.delete("/comunicados/{com_id}")
def eliminar_comunicado(com_id: int,
                        user: dict = Depends(require_rol("admin"))):
    """Elimina un comunicado. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM comunicados WHERE id=%s", (com_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Comunicado no encontrado", 404)
    finally:
        conn.close()
    return ok(mensaje="Comunicado eliminado")
