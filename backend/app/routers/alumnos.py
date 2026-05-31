"""Gestión de alumnos.

El alumno se crea sin password (el admin solo carga la ficha). El alumno
luego se registra desde la pantalla de login con el mismo email para
fijar su contraseña.
"""
from fastapi import APIRouter, Depends

from ..database import get_connection
from ..dependencies import (get_chatbot_or_current_user, get_current_user,
                            is_chatbot, require_rol, require_role)
from ..schemas.alumnos import AlumnoCreate, AlumnoUpdate
from ..utils import serialize_row
from ..utils.responses import error

router = APIRouter(tags=["alumnos"])

_STAFF = ("admin", "administrativo")
_MODALIDADES = {"presencial", "virtual", "hibrido"}
_CATEGORIAS = {"regular", "acelerado", "especial", "intensivo"}


# ── Buscar (chatbot + búsqueda admin) ───────────────────────────────────────

@router.get("/alumnos/buscar")
def buscar_alumno(dni: str | None = None, email: str | None = None,
                  user: dict = Depends(get_chatbot_or_current_user)):
    """Busca un alumno por DNI o email. Usado por el chatbot."""
    if not dni and not email:
        raise error("Indicá dni o email", 400)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        base_select = (
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.telefono, "
            "       u.modalidad, c.nombre AS curso, c.monto_cuota, "
            "       c.modalidad AS modalidad_curso "
            "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
        )
        if dni:
            cursor.execute(base_select + "WHERE u.dni = %s AND u.rol = 'alumno'", (dni,))
        else:
            cursor.execute(base_select + "WHERE u.email = %s AND u.rol = 'alumno'", (email,))
        alumno = cursor.fetchone()
    finally:
        conn.close()
    if not alumno:
        raise error("Alumno no encontrado", 404)
    return {"ok": True, "alumno": alumno}


# ── Búsqueda completa con ficha (admin) ─────────────────────────────────────

@router.get("/alumnos/ficha")
def ficha_alumno(q: str, user: dict = Depends(require_rol(*_STAFF))):
    """Busca por nombre/apellido/DNI y devuelve ficha completa con cuotas."""
    q = (q or "").strip()
    if not q:
        raise error("Indicá un término de búsqueda", 400)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("UPDATE cuotas SET estado='vencida' "
                       "WHERE estado='pendiente' AND fecha_vencimiento < CURDATE()")
        conn.commit()

        like = f"%{q}%"
        cursor.execute(
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.telefono, "
            "       u.curso_id, u.modalidad, c.nombre AS curso, "
            "       c.modalidad AS modalidad_curso, c.categoria AS categoria_curso, "
            "       u.creado_en "
            "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
            "WHERE u.rol='alumno' AND ("
            "       u.nombre LIKE %s OR u.apellido LIKE %s OR u.dni LIKE %s) "
            "ORDER BY u.apellido, u.nombre LIMIT 25",
            (like, like, like),
        )
        alumnos = cursor.fetchall()

        if not alumnos:
            return {"ok": True, "resultados": []}

        ids = tuple(a["id"] for a in alumnos)
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT alumno_id, estado, monto FROM cuotas "
            f"WHERE alumno_id IN ({placeholders})",
            ids,
        )
        cuotas_por_alumno: dict = {}
        for row in cursor.fetchall():
            d = cuotas_por_alumno.setdefault(
                row["alumno_id"], {"pagadas": 0, "pendientes": 0,
                                   "vencidas": 0, "deuda": 0.0})
            estado = row["estado"]
            if estado == "pagada":
                d["pagadas"] += 1
            elif estado == "vencida":
                d["vencidas"] += 1
                d["deuda"] += float(row["monto"])
            else:
                d["pendientes"] += 1
                d["deuda"] += float(row["monto"])
    finally:
        conn.close()

    resultados = []
    for a in alumnos:
        cuotas = cuotas_por_alumno.get(a["id"], {
            "pagadas": 0, "pendientes": 0, "vencidas": 0, "deuda": 0.0,
        })
        cuotas["deuda"] = round(cuotas["deuda"], 2)
        a["creado_en"] = str(a["creado_en"]) if a.get("creado_en") else None
        a["cuotas"] = cuotas
        resultados.append(a)
    return {"ok": True, "resultados": resultados}


# ── Listado completo ─────────────────────────────────────────────────────────

@router.get("/alumnos")
def listar_alumnos(
    curso_id: int | None = None,
    modalidad: str | None = None,
    categoria: str | None = None,
    buscar: str | None = None,
    estado: str | None = None,
    page: int = 1,
    per_page: int = 0,
    user: dict = Depends(require_rol(*_STAFF)),
):
    """Lista alumnos con filtros opcionales.

    Parámetros nuevos:
      - buscar: busca por nombre, apellido, email o DNI (LIKE %term%)
      - estado: filtro derivado:
          activo    → tiene password (se registró)
          pendiente → password IS NULL (aún no se registró)
          sin_curso → no tiene curso asignado
      - page / per_page: paginación (per_page=0 → sin paginar)
    """
    sql_base = (
        "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.telefono, "
        "       u.curso_id, u.modalidad, u.password IS NOT NULL AS registrado, "
        "       c.nombre AS curso, "
        "       c.modalidad AS modalidad_curso, c.categoria AS categoria_curso "
        "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
        "WHERE u.rol='alumno'"
    )
    params: list = []

    if curso_id is not None:
        sql_base += " AND u.curso_id = %s"
        params.append(curso_id)
    if modalidad and modalidad in _MODALIDADES:
        sql_base += " AND COALESCE(u.modalidad, c.modalidad) = %s"
        params.append(modalidad)
    if categoria and categoria in _CATEGORIAS:
        sql_base += " AND c.categoria = %s"
        params.append(categoria)

    # Búsqueda por texto libre
    if buscar and buscar.strip():
        term = f"%{buscar.strip()}%"
        sql_base += (
            " AND (u.nombre LIKE %s OR u.apellido LIKE %s "
            "OR u.email LIKE %s OR u.dni LIKE %s)"
        )
        params.extend([term, term, term, term])

    # Estado derivado
    _ESTADOS = {"activo", "pendiente", "sin_curso"}
    if estado and estado in _ESTADOS:
        if estado == "activo":
            sql_base += " AND u.password IS NOT NULL"
        elif estado == "pendiente":
            sql_base += " AND u.password IS NULL"
        elif estado == "sin_curso":
            sql_base += " AND u.curso_id IS NULL"

    # Count total before pagination
    sql_count = f"SELECT COUNT(*) AS total FROM ({sql_base}) AS sub"

    sql_base += " ORDER BY u.apellido, u.nombre"

    # Pagination
    if per_page > 0:
        offset = (max(page, 1) - 1) * per_page
        sql_base += " LIMIT %s OFFSET %s"
        params_paginated = params + [per_page, offset]
    else:
        params_paginated = params

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql_count, params)
        total = cursor.fetchone()["total"]

        cursor.execute(sql_base, params_paginated)
        alumnos = cursor.fetchall()
    finally:
        conn.close()

    # Convert bool(registrado) for JSON serialization
    for a in alumnos:
        a["registrado"] = bool(a.get("registrado", False))

    return {"ok": True, "alumnos": alumnos, "total": total}


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/alumnos")
def crear_alumno(data: AlumnoCreate, user: dict = Depends(require_rol(*_STAFF))):
    """Crea la ficha de un alumno. Sin password — lo fija el alumno al registrarse.

    Si el body no incluye `modalidad`, se hereda de la modalidad del curso.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        modalidad = data.modalidad
        if modalidad is None:
            cursor_dict = conn.cursor(dictionary=True)
            cursor_dict.execute("SELECT modalidad FROM cursos WHERE id = %s",
                                (data.curso_id,))
            row = cursor_dict.fetchone()
            cursor_dict.close()
            if not row:
                raise error("Curso no encontrado", 404)
            modalidad = row["modalidad"]

        try:
            cursor.execute(
                "INSERT INTO usuarios "
                "(nombre, apellido, email, password, rol, dni, telefono, "
                " curso_id, modalidad, auth_provider) "
                "VALUES (%s, %s, %s, NULL, 'alumno', %s, %s, %s, %s, 'local')",
                (data.nombre, data.apellido, data.email,
                 data.dni, data.telefono, data.curso_id, modalidad),
            )
            conn.commit()
            new_id = cursor.lastrowid
        except Exception as e:
            if "Duplicate entry" in str(e):
                raise error("Email o DNI ya registrado", 409)
            raise error("Error interno al crear alumno", 500)
    finally:
        conn.close()
    return {"ok": True, "id": new_id,
            "mensaje": "Alumno creado. Pedile que se registre con este email para crear su contraseña."}


@router.get("/alumnos/{alumno_id}")
def obtener_alumno(alumno_id: int, user: dict = Depends(require_rol(*_STAFF))):
    """Retorna datos de un alumno por ID. Solo admin/administrativo."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT u.id, u.nombre, u.apellido, u.email, u.dni, u.telefono, "
            "       u.curso_id, u.modalidad, c.nombre AS curso, "
            "       c.modalidad AS modalidad_curso, c.categoria AS categoria_curso "
            "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
            "WHERE u.id = %s AND u.rol = 'alumno'",
            (alumno_id,),
        )
        alumno = cursor.fetchone()
    finally:
        conn.close()
    if not alumno:
        raise error("Alumno no encontrado", 404)
    return {"ok": True, "alumno": alumno}


@router.put("/alumnos/{alumno_id}")
def editar_alumno(alumno_id: int, data: AlumnoUpdate,
                  user: dict = Depends(require_rol(*_STAFF))):
    """Edita campos parciales de un alumno."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE id = %s AND rol = 'alumno'",
                       (alumno_id,))
        alumno = cursor.fetchone()
        if not alumno:
            raise error("Alumno no encontrado", 404)

        nombre    = data.nombre    if data.nombre    is not None else alumno["nombre"]
        apellido  = data.apellido  if data.apellido  is not None else alumno.get("apellido")
        email     = str(data.email) if data.email   is not None else alumno["email"]
        dni       = data.dni       if data.dni       is not None else alumno.get("dni")
        telefono  = data.telefono  if data.telefono  is not None else alumno.get("telefono")
        curso_id  = data.curso_id  if data.curso_id  is not None else alumno.get("curso_id")
        modalidad = data.modalidad if data.modalidad is not None else alumno.get("modalidad")

        cursor.execute(
            "UPDATE usuarios SET nombre=%s, apellido=%s, email=%s, dni=%s, "
            "                    telefono=%s, curso_id=%s, modalidad=%s "
            "WHERE id=%s",
            (nombre, apellido, email, dni, telefono, curso_id, modalidad, alumno_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/alumnos/{alumno_id}")
def eliminar_alumno(alumno_id: int, user: dict = Depends(require_role("admin"))):
    """Elimina un alumno. Solo admin."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM usuarios WHERE id = %s AND rol = 'alumno'",
                       (alumno_id,))
        conn.commit()
        if not cursor.rowcount:
            raise error("Alumno no encontrado", 404)
    finally:
        conn.close()
    return {"ok": True}


# ── Cuotas (chatbot/staff/dueño) ─────────────────────────────────────────────

@router.get("/alumnos/{alumno_id}/cuotas")
def cuotas_por_alumno(alumno_id: int,
                      user: dict = Depends(get_chatbot_or_current_user)):
    """Resumen de cuotas de un alumno. Usado por el chatbot."""
    if is_chatbot(user):
        if user.get("chatbot_alumno_id") != alumno_id:
            raise error("alumno_id no coincide con la sesión autenticada", 403)
    elif user.get("rol") not in _STAFF and user.get("id") != alumno_id:
        raise error("Sin permisos", 403)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM usuarios WHERE id = %s AND rol = 'alumno'",
                       (alumno_id,))
        if not cursor.fetchone():
            raise error("Alumno no encontrado", 404)

        cursor.execute(
            "UPDATE cuotas SET estado='vencida' "
            "WHERE alumno_id=%s AND estado='pendiente' AND fecha_vencimiento < CURDATE()",
            (alumno_id,),
        )
        conn.commit()

        cursor.execute(
            "SELECT id, concepto, monto, fecha_vencimiento, estado FROM cuotas "
            "WHERE alumno_id=%s ORDER BY fecha_vencimiento ASC",
            (alumno_id,),
        )
        cuotas = [serialize_row(c) for c in cursor.fetchall()]
    finally:
        conn.close()

    pagadas    = [c for c in cuotas if c["estado"] == "pagada"]
    pendientes = [c for c in cuotas if c["estado"] in ("pendiente", "vencida",
                                                       "pendiente_verificacion")]
    deuda      = sum(float(c["monto"]) for c in pendientes)

    return {
        "ok": True,
        "alumno_id": alumno_id,
        "resumen": {
            "estado": "Al día" if not pendientes else "Con deuda",
            "cuotas_pagadas": len(pagadas),
            "cuotas_pendientes": len(pendientes),
            "deuda_total": round(deuda, 2),
        },
        "pendientes": pendientes,
    }
