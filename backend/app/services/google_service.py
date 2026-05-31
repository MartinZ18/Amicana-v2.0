"""Login con Google OAuth 2.0 (authorization code flow).

Centraliza:
- Construcción de la URL de consent (con state CSRF).
- Intercambio del code por access_token contra googleapis.
- Llamada a /userinfo para obtener email + sub + name.
- Resolución `get_or_create_user` que:
    * crea usuario nuevo (rol=alumno, password=NULL, auth_provider=google)
    * o vincula google_id a una cuenta local existente con el mismo email.

No expone HTTP — los routers se encargan de redirigir.
"""
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from ..auth import create_access_token
from ..database import get_connection
from . import auditoria_service


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = "openid email profile"


def _client_id() -> str:
    val = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not val:
        raise HTTPException(
            status_code=503,
            detail={"ok": False, "mensaje": "Login con Google no está configurado"},
        )
    return val


def _client_secret() -> str:
    val = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not val:
        raise HTTPException(
            status_code=503,
            detail={"ok": False, "mensaje": "Login con Google no está configurado"},
        )
    return val


def _redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/auth/google/callback",
    )


def post_login_redirect() -> str:
    """A dónde mandamos al usuario tras el callback exitoso (con ?token=)."""
    return os.environ.get(
        "GOOGLE_POST_LOGIN_REDIRECT",
        "http://localhost:8000/app/index.html",
    )


def get_authorization_url() -> tuple[str, str]:
    """Devuelve `(url, state)`. Guardar el state en la sesión del usuario
    para validarlo en el callback (defensa CSRF)."""
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "online",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}", state


async def exchange_code_for_token(code: str) -> dict:
    """Cambia `code` por `access_token`. Lanza HTTPException si Google rechaza."""
    payload = {
        "code": code,
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "redirect_uri": _redirect_uri(),
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data=payload)
    except httpx.TimeoutException:
        auditoria_service.registrar(None, "error_api_externa", "Timeout en Google token")
        raise HTTPException(
            status_code=504,
            detail={"ok": False, "mensaje": "El servicio de Google no responde"},
        )
    except httpx.RequestError as e:
        auditoria_service.registrar(None, "error_api_externa", f"Google token req error: {e}")
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "mensaje": "Error al contactar Google"},
        )

    if r.status_code >= 400:
        auditoria_service.registrar(None, "error_api_externa",
                                    f"Google token status={r.status_code}")
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "mensaje": "Google rechazó el código de autorización"},
        )

    data = r.json()
    if not data.get("access_token"):
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "mensaje": "Respuesta inválida de Google"},
        )
    return data


async def get_userinfo(access_token: str) -> dict:
    """Devuelve `{email, sub, name, ...}` o lanza HTTPException."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(GOOGLE_USERINFO_URL, headers=headers)
    except httpx.TimeoutException:
        auditoria_service.registrar(None, "error_api_externa", "Timeout en Google userinfo")
        raise HTTPException(
            status_code=504,
            detail={"ok": False, "mensaje": "El servicio de Google no responde"},
        )
    except httpx.RequestError as e:
        auditoria_service.registrar(None, "error_api_externa",
                                    f"Google userinfo req error: {e}")
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "mensaje": "Error al contactar Google"},
        )

    if r.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "mensaje": "No se pudo verificar la identidad"},
        )
    if r.status_code >= 400:
        auditoria_service.registrar(None, "error_api_externa",
                                    f"Google userinfo status={r.status_code}")
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "mensaje": "Error obteniendo datos de Google"},
        )

    data = r.json()
    if not data.get("email") or not data.get("id"):
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "mensaje": "No se pudo verificar la identidad"},
        )
    return data


def get_or_create_user(userinfo: dict) -> dict:
    """Resuelve el usuario AMICANA correspondiente al userinfo de Google.

    1. Si existe usuario con ese google_id → lo devuelve.
    2. Si no, busca por email → vincula el google_id (cuenta local existente).
    3. Si tampoco, crea nuevo usuario rol='alumno' con password=NULL.
    """
    email = userinfo["email"]
    google_sub = userinfo["id"]
    nombre = userinfo.get("name") or email.split("@")[0]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE google_id=%s", (google_sub,))
        user = cursor.fetchone()
        if user:
            return _to_user_dict(user)

        cursor.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
        user = cursor.fetchone()
        if user:
            cursor.execute(
                "UPDATE usuarios SET google_id=%s, auth_provider='google' WHERE id=%s",
                (google_sub, user["id"]),
            )
            conn.commit()
            user["google_id"] = google_sub
            user["auth_provider"] = "google"
            auditoria_service.registrar(email, "google_login_vincular",
                                        f"Cuenta local vinculada a Google sub={google_sub}")
            return _to_user_dict(user)

        cursor.execute(
            "INSERT INTO usuarios (nombre, email, password, rol, google_id, auth_provider) "
            "VALUES (%s, %s, NULL, 'alumno', %s, 'google')",
            (nombre, email, google_sub),
        )
        conn.commit()
        new_id = cursor.lastrowid
        auditoria_service.registrar(email, "google_login_crear",
                                    f"Usuario nuevo creado por Google sub={google_sub}")
        return {"id": new_id, "nombre": nombre, "email": email, "rol": "alumno"}
    finally:
        conn.close()


def _to_user_dict(row: dict) -> dict:
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "email": row["email"],
        "rol": row["rol"],
    }


def emitir_token(user: dict) -> str:
    """JWT con el mismo payload que el login normal."""
    return create_access_token({
        "sub": user["email"], "rol": user["rol"], "id": user["id"],
    })


async def handle_callback(code: str, expected_state: Optional[str],
                          received_state: Optional[str]) -> tuple[str, dict]:
    """Flujo completo: code → token → userinfo → user → JWT.

    Devuelve `(jwt, user)`. Lanza HTTPException ante cualquier error.
    """
    if not expected_state or received_state != expected_state:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "mensaje": "State inválido (posible CSRF)"},
        )
    token_data = await exchange_code_for_token(code)
    userinfo = await get_userinfo(token_data["access_token"])
    user = get_or_create_user(userinfo)
    jwt_token = emitir_token(user)
    auditoria_service.registrar(user["email"], "google_login_exitoso",
                                f"rol={user['rol']}")
    return jwt_token, user
