"""Perfil del alumno autenticado.

- GET /perfil  → datos del propio usuario.
- PUT /perfil  → editar telefono y/o email del propio usuario.
                 Nombre, DNI y rol NO se modifican desde acá.
"""
from fastapi import APIRouter, Depends

from ..auth import hash_password, verify_password
from ..database import get_connection
from ..dependencies import get_current_user
from ..schemas.perfil import (CompletarPerfilInput, PasswordUpdate, PerfilUpdate,
                              SetearPasswordInput)
from ..services import auditoria_service
from ..utils.responses import error, ok

router = APIRouter(tags=["perfil"])


@router.get("/perfil")
def ver_perfil(user: dict = Depends(get_current_user)):
    """Devuelve los datos del usuario autenticado."""
    email = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT u.id, u.nombre, u.email, u.rol, u.dni, u.telefono, "
            "       u.modalidad, u.auth_provider, "
            "       (u.password IS NOT NULL) AS tiene_password_local, "
            "       c.nombre AS curso, c.modalidad AS modalidad_curso "
            "FROM usuarios u LEFT JOIN cursos c ON u.curso_id = c.id "
            "WHERE u.email = %s",
            (email,),
        )
        perfil = cursor.fetchone()
    finally:
        conn.close()
    if not perfil:
        raise error("Usuario no encontrado", 404)
    perfil["tiene_password_local"] = bool(perfil.get("tiene_password_local"))
    return ok(data=perfil)


@router.put("/perfil")
def editar_perfil(data: PerfilUpdate, user: dict = Depends(get_current_user)):
    """Actualiza telefono y/o email del usuario autenticado.

    Si cambia el email, valida que no esté tomado por otra cuenta.
    """
    if data.telefono is None and data.email is None:
        raise error("Indicá al menos un campo a actualizar (telefono o email)", 400)

    email_actual = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, email, telefono FROM usuarios WHERE email=%s",
                       (email_actual,))
        row = cursor.fetchone()
        if not row:
            raise error("Usuario no encontrado", 404)

        nuevo_email = str(data.email) if data.email is not None else row["email"]
        nuevo_tel = data.telefono if data.telefono is not None else row["telefono"]

        if nuevo_email != row["email"]:
            cursor.execute(
                "SELECT id FROM usuarios WHERE email=%s AND id<>%s",
                (nuevo_email, row["id"]),
            )
            if cursor.fetchone():
                raise error("Ese email ya está en uso por otra cuenta", 409)

        cursor.execute(
            "UPDATE usuarios SET email=%s, telefono=%s WHERE id=%s",
            (nuevo_email, nuevo_tel, row["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    auditoria_service.registrar(email_actual, "editar_perfil",
                                f"telefono={'sí' if data.telefono else 'no'} "
                                f"email={'sí' if data.email else 'no'}")
    return ok(mensaje="Perfil actualizado")


@router.put("/perfil/completar")
def completar_perfil(data: CompletarPerfilInput, user: dict = Depends(get_current_user)):
    """Completa campos faltantes (dni, telefono, password) tras login con Google.

    - DNI: solo se escribe si el usuario aún no tiene uno registrado.
    - Teléfono: se actualiza siempre que se envíe.
    - Password: se hashea y guarda solo si actualmente es NULL (permite doble acceso Google + email).
    """
    if data.dni is None and data.telefono is None and data.password is None:
        raise error("Enviá al menos un campo (dni, telefono o password)", 400)

    email = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, dni, telefono, password FROM usuarios WHERE email=%s", (email,))
        row = cursor.fetchone()
        if not row:
            raise error("Usuario no encontrado", 404)

        sets, params = [], []
        if data.dni is not None and not row["dni"]:
            sets.append("dni=%s")
            params.append(data.dni)
        if data.telefono is not None:
            sets.append("telefono=%s")
            params.append(data.telefono)
        if data.password is not None and not row["password"]:
            sets.append("password=%s")
            params.append(hash_password(data.password))

        if not sets:
            return ok(mensaje="No hay campos nuevos para actualizar")

        params.append(row["id"])
        cursor.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()

    auditoria_service.registrar(email, "completar_perfil_google",
                                f"campos: {', '.join(s.split('=')[0] for s in sets)}")
    return ok(mensaje="Perfil completado")


@router.put("/perfil/password")
def cambiar_password(data: PasswordUpdate, user: dict = Depends(get_current_user)):
    """Cambia la contraseña del usuario autenticado.

    Bloquea si aún no hay una contraseña definida (cuentas Google que no la completaron).
    Si el usuario Google seteó una contraseña via /perfil/completar, puede cambiarla acá.
    """
    if data.password_actual == data.password_nueva:
        raise error("La nueva contraseña debe ser distinta a la actual", 400)

    email = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, password, auth_provider FROM usuarios WHERE email=%s",
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            raise error("Usuario no encontrado", 404)

        if not row.get("password"):
            raise error(
                "Tu cuenta no tiene una contraseña definida. "
                "Podés setear una desde tu perfil.",
                400,
            )

        if not verify_password(data.password_actual, row["password"]):
            raise error("La contraseña actual es incorrecta", 401)

        nueva_hash = hash_password(data.password_nueva)
        cursor.execute(
            "UPDATE usuarios SET password=%s WHERE id=%s",
            (nueva_hash, row["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    auditoria_service.registrar(email, "cambiar_password", "ok")
    return ok(mensaje="Contraseña actualizada")


@router.post("/perfil/setear-password")
def setear_password(data: SetearPasswordInput, user: dict = Depends(get_current_user)):
    """Setea una contraseña para cuentas Google que aún no la tienen.

    409 si ya existe una contraseña — usar PUT /perfil/password para cambiarla.
    """
    email = user.get("sub")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, password FROM usuarios WHERE email=%s", (email,))
        row = cursor.fetchone()
        if not row:
            raise error("Usuario no encontrado", 404)

        if row.get("password") is not None:
            raise error("Ya tenés una contraseña definida. Usá cambiar contraseña.", 409)

        cursor.execute(
            "UPDATE usuarios SET password=%s WHERE id=%s",
            (hash_password(data.password), row["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    auditoria_service.registrar(email, "setear_password_local", "ok")
    return ok(mensaje="Contraseña establecida")
