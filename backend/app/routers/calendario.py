"""Calendario de clases.

- GET    /calendario              → todos los autenticados (alumno ve solo
                                    las de su curso si no manda `curso_id`).
- GET    /calendario/{id}         → mismo criterio.
- POST   /calendario              → admin/administrativo.
- PUT    /calendario/{id}         → admin/administrativo.
- DELETE /calendario/{id}         → admin/administrativo.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..database import get_connection
from ..dependencies import get_current_user, require_rol
from ..schemas.calendario import ClaseCreate, ClaseUpdate
from ..utils.responses import error, ok

router = APIRouter(tags=["calendario"])

_STAFF = ("admin", "administrativo")


def _serializar_clase(row: dict) -> dict:
    return {
        "id": row["id"],
        "curso_id": row["curso_id"],
        "curso": row.get("curso"),
        "titulo": row["titulo"],
        "fecha": str(row["fecha"]),
        "hora_inicio": str(row["hora_inicio"]),
        "hora_fin": str(row["hora_fin"]),
        "descripcion": row.get("descripcion"),
    }


@router.get("/calendario")
def listar_clases(
    curso_id: Optional[int] = Query(default=None),
    desde:    Optional[date] = Query(default=None),
    hasta:    Optional[date] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Lista clases. El alumno solo ve las de su curso (curso_id forzado).

    Sin filtros: devuelve clases de los próximos 60 días.
    """
    if user.get("rol") == "alumno":
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT curso_id FROM usuarios WHERE id=%s",
                           (user.get("id"),))
            row = cursor.fetchone()
        finally:
            conn.close()
        if not row or not row["curso_id"]:
            return ok(data={"clases": [], "total": 0,
                            "mensaje": "Aún no estás inscripto en un curso."})
        curso_id = row["curso_id"]

    if not desde:
        desde = date.today()
    if not hasta:
        hasta = desde + timedelta(days=60)

    sql = ("SELECT cl.id, cl.curso_id, cl.titulo, cl.fecha, cl.hora_inicio, "
           "       cl.hora_fin, cl.descripcion, c.nombre AS curso "
           "FROM calendario_clases cl JOIN cursos c ON c.id = cl.curso_id "
           "WHERE cl.fecha BETWEEN %s AND %s")
    params: list = [desde, hasta]
    if curso_id is not None:
        sql += " AND cl.curso_id = %s"
        params.append(curso_id)
    sql += " ORDER BY cl.fecha ASC, cl.hora_inicio ASC"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, tuple(params))
        clases = [_serializar_clase(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return ok(data={"clases": clases, "total": len(clases)})


@router.post("/calendario")
def crear_clase(data: ClaseCreate, user: dict = Depends(require_rol(*_STAFF))):
    """Crea una clase en el calendario."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM cursos WHERE id=%s AND activo=1",
                       (data.curso_id,))
        if not cursor.fetchone():
            raise error("Curso inexistente o inactivo", 400)
        cursor.execute(
            "INSERT INTO calendario_clases "
            "(curso_id, titulo, fecha, hora_inicio, hora_fin, descripcion, creado_por) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (data.curso_id, data.titulo, data.fecha,
             data.hora_inicio, data.hora_fin, data.descripcion, user.get("id")),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    return ok(data={"id": new_id}, mensaje="Clase creada")


@router.put("/calendario/{clase_id}")
def editar_clase(clase_id: int, data: ClaseUpdate,
                 user: dict = Depends(require_rol(*_STAFF))):
    """Edita campos parciales de una clase."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM calendario_clases WHERE id=%s", (clase_id,))
        row = cursor.fetchone()
        if not row:
            raise error("Clase no encontrada", 404)

        curso_id    = data.curso_id    if data.curso_id    is not None else row["curso_id"]
        titulo      = data.titulo      if data.titulo      is not None else row["titulo"]
        fecha       = data.fecha       if data.fecha       is not None else row["fecha"]
        hora_inicio = data.hora_inicio if data.hora_inicio is not None else row["hora_inicio"]
        hora_fin    = data.hora_fin    if data.hora_fin    is not None else row["hora_fin"]
        descripcion = data.descripcion if data.descripcion is not None else row.get("descripcion")

        cursor.execute(
            "UPDATE calendario_clases SET curso_id=%s, titulo=%s, fecha=%s, "
            "hora_inicio=%s, hora_fin=%s, descripcion=%s WHERE id=%s",
            (curso_id, titulo, fecha, hora_inicio, hora_fin, descripcion, clase_id),
        )
        conn.commit()
    finally:
        conn.close()
    return ok(mensaje="Clase actualizada")


@router.delete("/calendario/{clase_id}")
def eliminar_clase(clase_id: int, user: dict = Depends(require_rol(*_STAFF))):
    """Elimina una clase del calendario."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM calendario_clases WHERE id=%s", (clase_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Clase no encontrada", 404)
    finally:
        conn.close()
    return ok(mensaje="Clase eliminada")
