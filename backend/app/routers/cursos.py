"""Gestión de cursos.

Las respuestas mantienen el formato `{"ok": True, "cursos": [...]}` /
`{"ok": True, "id": ...}` para no romper el frontend existente.
"""
from typing import Optional

from fastapi import APIRouter, Depends

from ..auth import get_current_user, require_role
from ..database import get_connection
from ..schemas.cursos import CursoCreate, CursoUpdate
from ..utils.responses import error

router = APIRouter(prefix="/cursos", tags=["cursos"])

_MODALIDADES = {"presencial", "virtual", "hibrido"}
_CATEGORIAS = {"regular", "acelerado", "especial", "intensivo"}


@router.get("")
def listar_cursos(
    categoria: Optional[str] = None,
    modalidad: Optional[str] = None,
    activo: Optional[bool] = None,
    user: dict = Depends(get_current_user),
):
    """Lista cursos con filtros opcionales por categoría, modalidad y activo."""
    sql = "SELECT * FROM cursos"
    where: list[str] = []
    params: list = []

    if categoria and categoria in _CATEGORIAS:
        where.append("categoria = %s")
        params.append(categoria)
    if modalidad and modalidad in _MODALIDADES:
        where.append("modalidad = %s")
        params.append(modalidad)
    if activo is not None:
        where.append("activo = %s")
        params.append(1 if activo else 0)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY nombre"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        cursos = cursor.fetchall()
    finally:
        conn.close()
    return {"ok": True, "cursos": cursos}


@router.post("")
def crear_curso(data: CursoCreate, user: dict = Depends(require_role("admin"))):
    """Crea un curso nuevo. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO cursos (nombre, descripcion, monto_cuota, modalidad, categoria, activo) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (data.nombre, data.descripcion, data.monto_cuota,
             data.modalidad, data.categoria, data.activo),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return {"ok": True, "id": new_id}
    except Exception as e:
        if "Duplicate entry" in str(e):
            raise error("Ya existe un curso con ese nombre", 409)
        raise error("Error interno al crear curso", 500)
    finally:
        conn.close()


@router.put("/{curso_id}")
def editar_curso(curso_id: int, data: CursoUpdate,
                 user: dict = Depends(require_role("admin"))):
    """Edita campos de un curso. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM cursos WHERE id = %s", (curso_id,))
        curso = cursor.fetchone()
        if not curso:
            raise error("Curso no encontrado", 404)

        nombre      = data.nombre      if data.nombre      is not None else curso["nombre"]
        descripcion = data.descripcion if data.descripcion is not None else curso["descripcion"]
        monto_cuota = data.monto_cuota if data.monto_cuota is not None else curso["monto_cuota"]
        modalidad   = data.modalidad   if data.modalidad   is not None else curso["modalidad"]
        categoria   = data.categoria   if data.categoria   is not None else curso["categoria"]
        activo      = data.activo      if data.activo      is not None else curso["activo"]

        cursor.execute(
            "UPDATE cursos SET nombre=%s, descripcion=%s, monto_cuota=%s, "
            "                  modalidad=%s, categoria=%s, activo=%s "
            "WHERE id=%s",
            (nombre, descripcion, monto_cuota, modalidad, categoria, activo, curso_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/{curso_id}")
def eliminar_curso(curso_id: int, user: dict = Depends(require_role("admin"))):
    """Elimina un curso. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM cursos WHERE id = %s", (curso_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Curso no encontrado", 404)
        return {"ok": True}
    finally:
        conn.close()
