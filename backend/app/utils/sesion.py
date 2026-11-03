"""Sesión en cookie httpOnly: cookies, protección CSRF y chequeo de Origin.

- `amicana_session`: el JWT, HttpOnly (el JS no lo lee).
- `amicana_csrf`: HMAC-SHA256(SECRET_KEY, JWT de la sesión), legible por JS. Las requests
  inseguras autenticadas por cookie tienen que repetirlo en el header `X-CSRF-Token`
  (double-submit firmado). El valor esperado se recalcula desde la cookie de sesión: la cookie
  amicana_csrf solo existe para que el JS lo lea, nunca se confía en ella.
- Bearer y X-Chatbot-Key no pasan por acá: el navegador no los manda solo.

Todo lo de cookies/CSRF/Origin vive en este módulo para no repartirlo por los routers.
"""
import hashlib
import hmac
import os
from typing import Iterable, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.responses import Response

SESSION_COOKIE = "amicana_session"
CSRF_COOKIE = "amicana_csrf"
CSRF_HEADER = "X-CSRF-Token"

METODOS_SEGUROS = ("GET", "HEAD", "OPTIONS")


def cookie_secure() -> bool:
    """Secure por defecto; solo SESSION_COOKIE_SECURE=0 (desarrollo/tests en http) lo apaga."""
    return os.environ.get("SESSION_COOKIE_SECURE", "1") != "0"


def csrf_de_sesion(token: str) -> str:
    """Token CSRF atado a esta sesión: HMAC-SHA256(SECRET_KEY, JWT)."""
    # Import diferido: auth.py importa este módulo.
    from ..auth import SECRET_KEY

    return hmac.new(SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def set_session_cookies(response: Response, token: str) -> None:
    """Setea la cookie de sesión (JWT) y la de CSRF, con la misma vida que el JWT."""
    # Import diferido: auth.py importa este módulo.
    from ..auth import ACCESS_TOKEN_EXPIRE_MINUTES

    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, path="/",
                        httponly=True, secure=cookie_secure(), samesite="lax")
    response.set_cookie(CSRF_COOKIE, csrf_de_sesion(token), max_age=max_age, path="/",
                        httponly=False, secure=cookie_secure(), samesite="lax")


def clear_session_cookies(response: Response) -> None:
    """Borra las dos cookies (mismos atributos que al setearlas, para que el navegador las pise)."""
    for nombre, httponly in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(nombre, path="/", httponly=httponly,
                               secure=cookie_secure(), samesite="lax")


def token_de_cookie(request: Request) -> Optional[str]:
    return request.cookies.get(SESSION_COOKIE) or None


def exigir_csrf(request: Request, token: str) -> None:
    """403 si el header X-CSRF-Token no es el HMAC de la sesión `token` (ya validada)."""
    if request.method in METODOS_SEGUROS:
        return
    header = request.headers.get(CSRF_HEADER, "")
    if not header or not hmac.compare_digest(csrf_de_sesion(token).encode(), header.encode()):
        raise HTTPException(status_code=403, detail="Token CSRF inválido o ausente")


def _origen_normalizado(origen: str) -> str:
    return origen.strip().rstrip("/").lower()


def origen_permitido(request: Request, origenes_cors: Iterable[str]) -> bool:
    """True si la request no trae Origin (cliente que no es navegador), o si es el propio host
    o uno de los orígenes de CORS.

    El propio origen se compara solo por host (y puerto): detrás del proxy de Railway el
    esquema que ve la app puede ser http aunque el navegador use https.
    """
    origen = request.headers.get("origin")
    if origen is None:
        return True
    if _origen_normalizado(origen) in {_origen_normalizado(o) for o in origenes_cors}:
        return True
    host = request.headers.get("host", "").strip().lower()
    return bool(host) and urlparse(origen).netloc.lower() == host
