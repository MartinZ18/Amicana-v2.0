"""Autenticación local (registro + login + me).

El prompt pide endpoints con prefijo `/auth/...`. Para no romper el
frontend ni los tests legacy (`/login`, `/usuarios`), se mantienen
ambos: los nuevos son la fuente de verdad y los legacy reusan la misma
lógica del service.

- POST /auth/register   (canónico) + POST /usuarios   (alias deprecated)
- POST /auth/login      (canónico) + POST /login      (alias deprecated)
- GET  /auth/me         (nuevo)
- POST /auth/logout     (nuevo)

Los logins, además de devolver el JWT en el body (clientes de API), lo dejan en la cookie
httpOnly `amicana_session` + `amicana_csrf` (ver utils/sesion.py).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import _optional_bearer, credenciales_de_usuario
from ..dependencies import get_current_user
from ..utils import sesion
from ..utils.rate_limit import limitar_login, limitar_registro
from ..schemas.auth import (LoginRequest, MeResponse, TokenResponse,
                            UsuarioCreate, UsuarioCreateLegacy)
from ..services import auth_service
from ..utils.responses import error, ok

router = APIRouter(tags=["auth"])

ROLES_PRIVILEGIADOS = ("admin", "administrativo")


def _exigir_admin_para_rol_privilegiado(rol: str, request: Request, bearer: Optional[str]) -> None:
    """Si se intenta crear un rol staff, exigir sesión (Bearer o cookie) de admin/administrativo."""
    if rol not in ROLES_PRIVILEGIADOS:
        return
    try:
        payload = credenciales_de_usuario(request, bearer)
    except HTTPException as e:
        # 401 por token inválido y 403 por CSRF; mismo formato {ok, mensaje} que el resto.
        raise error(str(e.detail), e.status_code)
    if payload is None:
        raise error("Se requiere autenticación admin para crear roles privilegiados", 403)
    if payload.get("rol") not in ROLES_PRIVILEGIADOS:
        raise error("Solo admin puede crear roles privilegiados", 403)


# ── /auth/register (canónico) ──────────────────────────────────────────────

@router.post("/auth/register", dependencies=[Depends(limitar_registro)])
def register(usuario: UsuarioCreate, request: Request,
             token: Optional[str] = Depends(_optional_bearer)):
    """Registra un usuario nuevo. Por defecto rol=alumno; staff requiere JWT admin."""
    _exigir_admin_para_rol_privilegiado(usuario.rol, request, token)
    try:
        creado = auth_service.registrar_usuario(
            usuario.nombre, usuario.email, usuario.password, usuario.rol,
        )
    except ValueError as e:
        raise error(str(e), 409)
    return ok(data={"id": creado["id"], "email": creado["email"], "rol": creado["rol"]},
              mensaje="Usuario creado correctamente")


# ── /auth/login (canónico, JSON) ───────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse,
             dependencies=[Depends(limitar_login)])
def login_json(req: LoginRequest, response: Response):
    """Login con email + password (JSON). Devuelve JWT + rol y setea la cookie de sesión."""
    try:
        result = auth_service.autenticar(req.email, req.password)
    except LookupError:
        raise error("Usuario no encontrado", 400)
    except PermissionError as e:
        raise error(str(e), 400)
    except ValueError:
        raise error("Contraseña incorrecta", 400)

    sesion.set_session_cookies(response, result["access_token"])
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


# ── /auth/logout ───────────────────────────────────────────────────────────

# Sin guard ni CSRF a propósito: es idempotente (sin sesión también limpia y responde 200) y un
# logout forzado es inofensivo. El middleware de Origin igual frena los pedidos de otros sitios.
@router.post("/auth/logout")
def logout(response: Response):
    """Borra las cookies de sesión y de CSRF."""
    sesion.clear_session_cookies(response)
    return ok(mensaje="Sesión cerrada")


# ── ALIAS LEGACY: /usuarios + /login (mantenidos para no romper) ───────────
# legacy: no migrar — estos endpoints usan HTTPException plano para no romper
# tests legacy ni el frontend actual que lee `data.detail` directamente.

@router.post("/usuarios", deprecated=True, dependencies=[Depends(limitar_registro)])
def crear_usuario_legacy(usuario: UsuarioCreateLegacy, request: Request,
                         token: Optional[str] = Depends(_optional_bearer)):
    """[DEPRECATED] Alias de POST /auth/register. Usar /auth/register.

    Difiere solo en validaciones: este alias acepta `password` desde 6
    caracteres y no exige número (compatibilidad con frontend actual).
    """
    _exigir_admin_para_rol_privilegiado(usuario.rol, request, token)
    try:
        auth_service.registrar_usuario(
            usuario.nombre, usuario.email, usuario.password, usuario.rol,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="El email ya está registrado")
    return {"mensaje": "Usuario creado"}


@router.post("/login", deprecated=True, dependencies=[Depends(limitar_login)])
def login_form_legacy(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """[DEPRECATED] Alias de POST /auth/login. Usar /auth/login."""
    try:
        result = auth_service.autenticar(form_data.username, form_data.password)
    except LookupError:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="Contraseña incorrecta")
    sesion.set_session_cookies(response, result["access_token"])
    return {"access_token": result["access_token"], "token_type": "bearer"}
