"""Lógica de auth (registro, login, hash) sin acoplarse al transport.

Los routers (routers/auth.py) solo arman el HTTP request/response y
delegan acá la lógica real. Esto facilita los tests y mantiene la regla
"routers finos / services gordos".
"""
from typing import Optional

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_connection
from . import auditoria_service


def buscar_usuario_por_email(email: str) -> Optional[dict]:
    """Devuelve la fila completa del usuario o None."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
        return cursor.fetchone()
    finally:
        conn.close()


def email_existe(email: str) -> bool:
    """True si ya hay un usuario con ese email."""
    return buscar_usuario_por_email(email) is not None


def registrar_usuario(nombre: str, email: str, password: str, rol: str) -> dict:
    """Crea un usuario local nuevo y devuelve `{id, email, rol}`.

    Normaliza el email a minúsculas antes de guardar y de chequear duplicados.
    Lanza ValueError si el email ya existe — el router lo convierte en 409.
    """
    email = email.lower().strip()

    if email_existe(email):
        raise ValueError("El email ya está registrado")

    hashed = hash_password(password)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (nombre, email, password, rol, auth_provider) "
            "VALUES (%s, %s, %s, %s, 'local')",
            (nombre, email, hashed, rol),
        )
        conn.commit()
        new_id = cursor.lastrowid
    finally:
        conn.close()

    auditoria_service.registrar(email, "registro_usuario", f"rol={rol} auth_provider=local")
    return {"id": new_id, "email": email, "rol": rol, "nombre": nombre}


def autenticar(email: str, password: str) -> dict:
    """Valida credenciales y devuelve `{access_token, rol, id, nombre}`.

    Lanza:
      - LookupError si el usuario no existe.
      - PermissionError si la cuenta es OAuth (password NULL en BD).
      - ValueError si la contraseña no coincide.
    """
    user = buscar_usuario_por_email(email)
    if not user:
        auditoria_service.registrar(email, "login_fallido", "usuario inexistente")
        raise LookupError("Usuario no encontrado")

    if user.get("password") is None:
        auditoria_service.registrar(email, "login_fallido", "cuenta google sin password local")
        raise PermissionError("Esta cuenta usa inicio de sesión con Google")

    if not verify_password(password, user["password"]):
        auditoria_service.registrar(email, "login_fallido", "password incorrecto")
        raise ValueError("Contraseña incorrecta")

    token = create_access_token({
        "sub": user["email"], "rol": user["rol"], "id": user["id"],
    })
    auditoria_service.registrar(email, "login_exitoso", f"rol={user['rol']}")
    return {
        "access_token": token,
        "rol": user["rol"],
        "id": user["id"],
        "nombre": user["nombre"],
    }


def perfil_de_token(payload: dict) -> Optional[dict]:
    """Devuelve los datos públicos del usuario asociado al JWT."""
    email = payload.get("sub")
    if not email:
        return None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, nombre, email, rol, dni, telefono, "
            "COALESCE(auth_provider, 'local') AS auth_provider "
            "FROM usuarios WHERE email=%s",
            (email,),
        )
        return cursor.fetchone()
    finally:
        conn.close()
