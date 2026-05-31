"""Autenticación local (registro + login + me).

El prompt pide endpoints con prefijo `/auth/...`. Para no romper el
frontend ni los tests legacy (`/login`, `/usuarios`), se mantienen
ambos: los nuevos son la fuente de verdad y los legacy reusan la misma
lógica del service.

- POST /auth/register   (canónico) + POST /usuarios   (alias deprecated)
- POST /auth/login      (canónico) + POST /login      (alias deprecated)
- GET  /auth/me         (nuevo)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from ..auth import ALGORITHM, SECRET_KEY
from ..dependencies import get_current_user
from ..schemas.auth import (LoginRequest, MeResponse, TokenResponse,
                            UsuarioCreate, UsuarioCreateLegacy)
from ..services import auth_service
from ..utils.responses import error, ok

router = APIRouter(tags=["auth"])

ROLES_PRIVILEGIADOS = ("admin", "administrativo")

_optional_bearer = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def _exigir_admin_para_rol_privilegiado(rol: str, token: Optional[str]) -> None:
    """Si se intenta crear un rol staff, exigir JWT de admin/administrativo."""
    if rol not in ROLES_PRIVILEGIADOS:
        return
    if not token:
        raise error("Se requiere autenticación admin para crear roles privilegiados", 403)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise error("Token inválido", 401)
    if payload.get("rol") not in ROLES_PRIVILEGIADOS:
        raise error("Solo admin puede crear roles privilegiados", 403)


# ── /auth/register (canónico) ──────────────────────────────────────────────

@router.post("/auth/register")
def register(usuario: UsuarioCreate,
             token: Optional[str] = Depends(_optional_bearer)):
    """Registra un usuario nuevo. Por defecto rol=alumno; staff requiere JWT admin."""
    _exigir_admin_para_rol_privilegiado(usuario.rol, token)
    try:
        creado = auth_service.registrar_usuario(
            usuario.nombre, usuario.email, usuario.password, usuario.rol,
        )
    except ValueError as e:
        raise error(str(e), 409)
    return ok(data={"id": creado["id"], "email": creado["email"], "rol": creado["rol"]},
              mensaje="Usuario creado correctamente")


# ── /auth/login (canónico, JSON) ───────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse)
def login_json(req: LoginRequest):
    """Login con email + password (JSON). Devuelve JWT + rol."""
    try:
        result = auth_service.autenticar(req.email, req.password)
    except LookupError:
        raise error("Usuario no encontrado", 400)
    except PermissionError as e:
        raise error(str(e), 400)
    except ValueError:
        raise error("Contraseña incorrecta", 400)

    return TokenResponse(
        access_token=result["access_token"],
        rol=result["rol"],
        nombre=result["nombre"],
        id=result["id"],
    )


# ── /auth/me ───────────────────────────────────────────────────────────────

@router.get("/auth/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user)):
    """Devuelve datos del usuario autenticado (sin password)."""
    perfil = auth_service.perfil_de_token(user)
    if not perfil:
        raise error("Usuario no encontrado", 404)
    return MeResponse(**perfil)


# ── ALIAS LEGACY: /usuarios + /login (mantenidos para no romper) ───────────
# legacy: no migrar — estos endpoints usan HTTPException plano para no romper
# tests legacy ni el frontend actual que lee `data.detail` directamente.

@router.post("/usuarios", deprecated=True)
def crear_usuario_legacy(usuario: UsuarioCreateLegacy,
                         token: Optional[str] = Depends(_optional_bearer)):
    """[DEPRECATED] Alias de POST /auth/register. Usar /auth/register.

    Difiere solo en validaciones: este alias acepta `password` desde 6
    caracteres y no exige número (compatibilidad con frontend actual).
    """
    _exigir_admin_para_rol_privilegiado(usuario.rol, token)
    try:
        auth_service.registrar_usuario(
            usuario.nombre, usuario.email, usuario.password, usuario.rol,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="El email ya está registrado")
    return {"mensaje": "Usuario creado"}


@router.post("/login", deprecated=True)
def login_form_legacy(form_data: OAuth2PasswordRequestForm = Depends()):
    """[DEPRECATED] Alias de POST /auth/login. Usar /auth/login."""
    try:
        result = auth_service.autenticar(form_data.username, form_data.password)
    except LookupError:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="Contraseña incorrecta")
    return {"access_token": result["access_token"], "token_type": "bearer"}
