from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from jwt import PyJWTError
import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv

from .utils import sesion

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está definida. Copiá .env.example a .env y configurala.")

CHATBOT_INTERNAL_KEY = os.environ.get("CHATBOT_INTERNAL_KEY")
if not CHATBOT_INTERNAL_KEY:
    raise RuntimeError("CHATBOT_INTERNAL_KEY no está definida. Copiá .env.example a .env y configurala.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
_optional_bearer = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def _decodificar(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


def credenciales_de_usuario(request: Request, bearer: Optional[str]) -> Optional[dict]:
    """Payload del JWT de la request: Bearer, o si no hay, la cookie de sesión.

    Devuelve None si no hay ninguna de las dos; 401 si la que hay es inválida (no se cae
    a la otra). Una sesión por cookie en un método inseguro exige además el header
    X-CSRF-Token; el Bearer no, porque el navegador no lo manda solo. Primero se valida
    el JWT (sesión inválida o vencida = 401) y recién después el CSRF.
    """
    if bearer:
        return _decodificar(bearer)
    token = sesion.token_de_cookie(request)
    if not token:
        return None
    payload = _decodificar(token)
    sesion.exigir_csrf(request, token)
    return payload


def jwt_de_sesion_valida(request: Request) -> Optional[str]:
    """El JWT de la cookie de sesión si es válido y está vigente; None si falta o no sirve.
    Nunca levanta: sirve para endpoints que son anónimos salvo que haya una sesión buena."""
    token = sesion.token_de_cookie(request)
    if not token:
        return None
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None
    return token


def get_current_user(request: Request, bearer: Optional[str] = Depends(_optional_bearer)):
    payload = credenciales_de_usuario(request, bearer)
    if payload is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return payload


def is_chatbot(user: dict) -> bool:
    """True si el user dict viene de la auth via X-Chatbot-Key.

    El sub solo no alcanza: un JWT lleva como sub el email del usuario y
    cualquiera puede registrarse con chatbot@amicana.com. El rol "chatbot" no
    existe en la BD, así que ningún JWT emitido por login lo puede traer.
    """
    return user.get("rol") == "chatbot" and user.get("sub") == "chatbot@amicana.com"


def get_chatbot_or_current_user(
    request: Request,
    token: Optional[str] = Depends(_optional_bearer),
):
    """Acepta JWT Bearer, X-Chatbot-Key (n8n) o la cookie de sesión, en ese orden."""
    if token:
        return _decodificar(token)
    chatbot_key = request.headers.get("X-Chatbot-Key")
    if chatbot_key and chatbot_key == CHATBOT_INTERNAL_KEY:
        chatbot_user = {"sub": "chatbot@amicana.com", "rol": "chatbot", "id": 0}
        session_id = request.headers.get("X-Chatbot-Session-Id")
        if session_id:
            # Importar dentro del request para evitar ciclos en boot.
            from .models.chat_session import ChatSessionRepository
            try:
                sess = ChatSessionRepository().get_by_session_id(session_id)
                if sess and sess.alumno_id:
                    chatbot_user["chatbot_alumno_id"] = sess.alumno_id
            except Exception as e:
                # No bloquear auth si BD no responde — el endpoint downstream
                # validará alumno_id contra la cuota igual.
                print(f"⚠️  No se pudo cargar la sesión chatbot {session_id}: {e}")
        return chatbot_user
    payload = credenciales_de_usuario(request, None)
    if payload is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return payload


def require_role(required_role: str):
    def role_checker(user: dict = Depends(get_current_user)):
        if user.get("rol") != required_role:
            raise HTTPException(status_code=403, detail="No tienes permisos suficientes")
        return user
    return role_checker


def require_any_role(*roles: str):
    """Dependencia reutilizable para endpoints que admiten varios roles."""
    def role_checker(user: dict = Depends(get_current_user)):
        if user.get("rol") not in roles:
            raise HTTPException(status_code=403, detail="Sin permisos")
        return user
    return role_checker