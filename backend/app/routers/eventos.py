"""Eventos institucionales (feriados, conmemoraciones, intercambios, etc).

A diferencia de `calendario_clases`, no están atados a un curso. Los alumnos
solo ven eventos con `visible_alumno = 1`.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..database import get_connection
from ..dependencies import get_current_user, require_rol
from ..schemas.eventos import EventoCreate, EventoUpdate
from ..utils.responses import error, ok

router = APIRouter(tags=["eventos"])

_STAFF = ("admin", "administrativo")


def _serializar(row: dict) -> dict:
    return {
        "id": row["id"],
        "titulo": row["titulo"],
        "descripcion": row.get("descripcion"),
        "tipo": row["tipo"],
        "fecha_inicio": str(row["fecha_inicio"]),
        "fecha_fin": str(row["fecha_fin"]) if row.get("fecha_fin") else None,
        "hora_inicio": str(row["hora_inicio"]) if row.get("hora_inicio") else None,
        "hora_fin": str(row["hora_fin"]) if row.get("hora_fin") else None,
        "todo_el_dia": bool(row["todo_el_dia"]),
        "visible_alumno": bool(row["visible_alumno"]),
        "creado_por": row.get("creado_por"),
    }


@router.get("/eventos")
def listar_eventos(
    desde: Optional[date] = Query(default=None),
    hasta: Optional[date] = Query(default=None),
    tipo:  Optional[str]  = Query(default=None),
    user:  dict = Depends(get_current_user),
):
    """Lista eventos institucionales. Alumnos solo ven los visibles.

    Sin filtros: devuelve eventos de los próximos 90 días.
    """
    if not desde:
        desde = date.today()
    if not hasta:
        hasta = desde + timedelta(days=90)

    sql = ("SELECT id, titulo, descripcion, tipo, fecha_inicio, fecha_fin, "
           "       hora_inicio, hora_fin, todo_el_dia, visible_alumno, creado_por "
           "FROM eventos_institucionales "
           "WHERE fecha_inicio <= %s AND COALESCE(fecha_fin, fecha_inicio) >= %s")
    params: list = [hasta, desde]
    if tipo:
        sql += " AND tipo = %s"
        params.append(tipo)
    if user.get("rol") not in _STAFF:
        sql += " AND visible_alumno = 1"
    sql += " ORDER BY fecha_inicio ASC, COALESCE(hora_inicio, '00:00:00') ASC"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, tuple(params))
        eventos = [_serializar(r) for r in cursor.fetchall()]
    finally:
        conn.close()
    return ok(data={"eventos": eventos, "total": len(eventos)})


@router.post("/eventos")
def crear_evento(data: EventoCreate, user: dict = Depends(require_rol(*_STAFF))):
    """Crea un evento institucional."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO eventos_institucionales "
            "(titulo, descripcion, tipo, fecha_inicio, fecha_fin, "
            " hora_inicio, hora_fin, todo_el_dia, visible_alumno, creado_por) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (data.titulo, data.descripcion, data.tipo,
             data.fecha_inicio, data.fecha_fin,
             data.hora_inicio, data.hora_fin,
             data.todo_el_dia, data.visible_alumno, user.get("id")),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()
    return ok(data={"id": new_id}, mensaje="Evento creado")


@router.put("/eventos/{evento_id}")
def editar_evento(evento_id: int, data: EventoUpdate,
                  user: dict = Depends(require_rol(*_STAFF))):
    """Edita campos parciales de un evento."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM eventos_institucionales WHERE id=%s",
                       (evento_id,))
        row = cursor.fetchone()
        if not row:
            raise error("Evento no encontrado", 404)

        titulo         = data.titulo         if data.titulo         is not None else row["titulo"]
        descripcion    = data.descripcion    if data.descripcion    is not None else row.get("descripcion")
        tipo           = data.tipo           if data.tipo           is not None else row["tipo"]
        fecha_inicio   = data.fecha_inicio   if data.fecha_inicio   is not None else row["fecha_inicio"]
        fecha_fin      = data.fecha_fin      if data.fecha_fin      is not None else row.get("fecha_fin")
        hora_inicio    = data.hora_inicio    if data.hora_inicio    is not None else row.get("hora_inicio")
        hora_fin       = data.hora_fin       if data.hora_fin       is not None else row.get("hora_fin")
        todo_el_dia    = data.todo_el_dia    if data.todo_el_dia    is not None else row["todo_el_dia"]
        visible_alumno = data.visible_alumno if data.visible_alumno is not None else row["visible_alumno"]

        if todo_el_dia:
            hora_inicio = None
            hora_fin = None

        cursor.execute(
            "UPDATE eventos_institucionales "
            "SET titulo=%s, descripcion=%s, tipo=%s, fecha_inicio=%s, fecha_fin=%s, "
            "    hora_inicio=%s, hora_fin=%s, todo_el_dia=%s, visible_alumno=%s "
            "WHERE id=%s",
            (titulo, descripcion, tipo, fecha_inicio, fecha_fin,
             hora_inicio, hora_fin, todo_el_dia, visible_alumno, evento_id),
        )
        conn.commit()
    finally:
        conn.close()
    return ok(mensaje="Evento actualizado")


@router.delete("/eventos/{evento_id}")
def eliminar_evento(evento_id: int, user: dict = Depends(require_rol(*_STAFF))):
    """Elimina un evento institucional."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM eventos_institucionales WHERE id=%s",
                       (evento_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Evento no encontrado", 404)
    finally:
        conn.close()
    return ok(mensaje="Evento eliminado")
