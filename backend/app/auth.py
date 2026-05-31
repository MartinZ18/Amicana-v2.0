from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está definida. Copiá .env.example a .env y configurala.")

CHATBOT_INTERNAL_KEY = os.environ.get("CHATBOT_INTERNAL_KEY", "amicana-internal")

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

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


def is_chatbot(user: dict) -> bool:
    """True si el user dict viene de la auth via X-Chatbot-Key."""
    return user.get("sub") == "chatbot@amicana.com"


def get_chatbot_or_current_user(
    request: Request,
    token: Optional[str] = Depends(_optional_bearer),
):
    """Acepta JWT Bearer o X-Chatbot-Key para llamadas internas de n8n."""
    if token:
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            raise HTTPException(status_code=401, detail="Token inválido")
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
    raise HTTPException(status_code=401, detail="No autenticado")


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