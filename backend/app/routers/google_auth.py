"""Login con Google OAuth 2.0.

Solo routing — toda la lógica vive en `services/google_service.py`.

Flujo:
  1. Frontend manda al usuario a GET /auth/google/login.
  2. Lo redirigimos al consent de Google con un `state` aleatorio guardado en cookie.
  3. Google redirige a GET /auth/google/callback?code=...&state=...
  4. Validamos state, intercambiamos code → token → userinfo, creamos/buscamos
     usuario, emitimos JWT, lo dejamos en las cookies de sesión (httpOnly + CSRF) y
     redirigimos al frontend SIN token en la URL.

El frontend consulta /auth/me para saber el rol y a dónde ir.
"""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..services import google_service
from ..utils import sesion
from ..utils.responses import error

router = APIRouter(tags=["auth-google"])

_STATE_COOKIE = "amicana_google_state"


@router.get("/auth/google/login")
async def google_login():
    """Redirige al consent screen de Google."""
    url, state = google_service.get_authorization_url()
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        _STATE_COOKIE, state,
        max_age=600, path="/", httponly=True, secure=sesion.cookie_secure(), samesite="lax",
    )
    return response


@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "",
                          error_param: str | None = None):
    """Procesa el callback de Google, deja la sesión en cookies y redirige al frontend."""
    qp = request.query_params
    google_error = qp.get("error") or error_param
    if google_error:
        raise error(f"Google rechazó el login: {google_error}", 400)
    if not code:
        raise error("Falta el código de autorización de Google", 400)

    expected_state = request.cookies.get(_STATE_COOKIE)
    jwt_token, _user = await google_service.handle_callback(
        code=code, expected_state=expected_state, received_state=state,
    )

    target = google_service.post_login_redirect()
    redirect = RedirectResponse(url=target, status_code=302)
    sesion.set_session_cookies(redirect, jwt_token)
    redirect.delete_cookie(_STATE_COOKIE, path="/", httponly=True,
                           secure=sesion.cookie_secure(), samesite="lax")
    return redirect
