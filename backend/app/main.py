import collections
import logging
import os
import threading
import time
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import hash_password
from .database import get_connection
from .utils.responses import error

logger = logging.getLogger("amicana")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

# Routers
from .routers import auth as auth_router
from .routers import google_auth as google_auth_router
from .routers import alumnos as alumnos_router
from .routers import cursos as cursos_router
from .routers import pagos as pagos_router
from .routers import chatbot as chatbot_router
from .routers import qr as qr_router
from .routers import avisos as avisos_router
from .routers import perfil as perfil_router
from .routers import calendario as calendario_router
from .routers import comunicados as comunicados_router
from .routers import reportes as reportes_router
from .routers import eventos as eventos_router
from .routers import configuracion as configuracion_router
from .routers import progreso as progreso_router
from .routers import chatbot_data as chatbot_data_router


# ── Lifespan: seed admin ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@amicana.com",))
        if cursor.fetchone() is None:
            seed_pw = os.environ.get("ADMIN_SEED_PASSWORD")
            if not seed_pw:
                print("⚠️  Admin seed omitido: definir ADMIN_SEED_PASSWORD en .env")
            else:
                hashed = hash_password(seed_pw)
                cursor.execute(
                    "INSERT INTO usuarios (nombre, email, password, rol) VALUES (%s, %s, %s, %s)",
                    ("Administrador", "admin@amicana.com", hashed, "admin")
                )
                conn.commit()
                print("[OK] Admin seed: usuario admin@amicana.com creado.")
        else:
            print("[INFO] Admin seed: admin@amicana.com ya existe, se omite.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Admin seed fallo (BD no disponible?): {e}")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="AMICANA 2.0", lifespan=lifespan)

# CORS: lista de orígenes permitidos, configurable vía env CORS_ORIGINS
# (CSV: "http://localhost:5173,https://app.amicana.com"). En desarrollo
# default permisivo de localhost; en producción definir explícitamente.
_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env.strip() == "*":
    cors_origins = ["*"]
elif _cors_env.strip():
    cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    cors_origins = [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
        "https://AmicanaProfesional.com",
        "https://AmicanaProfesional.com:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(google_auth_router.router)
app.include_router(alumnos_router.router)
app.include_router(cursos_router.router)
app.include_router(pagos_router.router)
app.include_router(pagos_router.pagos_root_router)
app.include_router(chatbot_router.router)
app.include_router(qr_router.router)
app.include_router(avisos_router.router)
app.include_router(perfil_router.router)
app.include_router(calendario_router.router)
app.include_router(comunicados_router.router)
app.include_router(reportes_router.router)
app.include_router(eventos_router.router)
app.include_router(configuracion_router.router)
app.include_router(progreso_router.router)
app.include_router(chatbot_data_router.router)

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# Dev: disable cache for HTML/CSS/JS so changes are picked up immediately
@app.middleware("http")
async def no_cache_frontend(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/app"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/Prueba")
def root():
    return {"mensaje": "AMICANA 2.0 funcionando 🔥"}


_RATE_LIMIT  = int(os.environ.get("CHATBOT_RATE_LIMIT", "30"))  # mensajes por ventana
_RATE_WINDOW = 3600  # segundos (1 hora)
_rate_buckets: dict = collections.defaultdict(list)  # session_id → [timestamps]


def _check_rate_limit(session_id: str) -> bool:
    """True si la sesión excedió el límite. Limpia entradas viejas."""
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW
    bucket = _rate_buckets[session_id]
    _rate_buckets[session_id] = [t for t in bucket if t > cutoff]
    if len(_rate_buckets[session_id]) >= _RATE_LIMIT:
        return True
    _rate_buckets[session_id].append(now)
    return False


def _normalize_chatbot_response(data) -> dict:
    """Convierte cualquier formato de n8n a {text, qr_url, pdf_url}."""
    if isinstance(data, str):
        return {"text": data, "qr_url": None, "pdf_url": None}
    if isinstance(data, dict):
        if "text" in data or "qr_url" in data or "pdf_url" in data:
            return {"text": data.get("text"), "qr_url": data.get("qr_url"), "pdf_url": data.get("pdf_url")}
        if "output" in data:
            out = data["output"]
            if isinstance(out, str):
                return {"text": out, "qr_url": None, "pdf_url": None}
            if isinstance(out, dict):
                return {"text": out.get("text"), "qr_url": out.get("qr_url"), "pdf_url": out.get("pdf_url")}
        if "message" in data:
            return {"text": data["message"], "qr_url": None, "pdf_url": None}
    return {"text": "Respuesta recibida pero sin formato reconocido.", "qr_url": None, "pdf_url": None}


@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    """Proxy del widget hacia n8n. Evita CORS: el browser solo habla con :8000.

    Cualquier error de red o respuesta vacía cae al fallback amigable y queda
    registrado con `logger.exception` para debug — el usuario ve un mensaje
    genérico, los operadores ven el traceback completo en logs.
    """
    import requests as req_lib

    _fallback = {
        "text": "El asistente no está disponible en este momento. Intentá de nuevo.",
        "qr_url": None,
        "pdf_url": None,
    }

    try:
        body = await request.json()
    except Exception:
        logger.warning("[chatbot proxy] body inválido o no-JSON desde el widget")
        return _fallback

    session_id = (body or {}).get("session_id", "<sin-session>")

    if _check_rate_limit(session_id):
        logger.warning("[chatbot proxy] rate limit excedido session=%s", session_id)
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse(status_code=429, content={
            "text": "Demasiados mensajes, esperá un minuto.",
            "qr_url": None, "pdf_url": None,
        })

    # Forward X-User-Token si el widget lo envía (pre-auth)
    user_token = request.headers.get("X-User-Token")
    if user_token and body:
        body = {**body, "user_token": user_token}

    n8n_url = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/amicana-chatbot")
    timeout_s = float(os.environ.get("N8N_TIMEOUT_SECONDS", "30"))

    started = time.monotonic()
    try:
        # `requests.post` es bloqueante: si se ejecuta directo en esta ruta
        # `async`, congela el event loop de uvicorn mientras espera a n8n.
        # El problema: el workflow de n8n llama DE VUELTA a este mismo FastAPI
        # (GET/POST /chatbot/session, /alumnos/buscar, etc.) durante su ejecución;
        # con el loop bloqueado esos callbacks no se atienden → n8n nunca responde
        # → timeout de 45s → deadlock. Lo descargamos al threadpool para que el
        # loop quede libre y pueda servir los callbacks de n8n en paralelo.
        r = await run_in_threadpool(
            lambda: req_lib.post(n8n_url, json=body, timeout=timeout_s,
                                 headers={"ngrok-skip-browser-warning": "true"})
        )
    except req_lib.exceptions.Timeout:
        logger.warning("[chatbot proxy] timeout (%ss) hacia n8n session=%s url=%s",
                       timeout_s, session_id, n8n_url)
        return _fallback
    except req_lib.exceptions.ConnectionError as e:
        logger.warning("[chatbot proxy] no se pudo conectar a n8n session=%s url=%s err=%s",
                       session_id, n8n_url, e)
        return _fallback
    except Exception:
        logger.exception("[chatbot proxy] error inesperado llamando a n8n session=%s", session_id)
        return _fallback

    elapsed_ms = int((time.monotonic() - started) * 1000)
    text = (r.text or "").strip()
    if not text:
        logger.warning("[chatbot proxy] body vacío de n8n status=%s session=%s elapsed=%sms",
                       r.status_code, session_id, elapsed_ms)
        return _fallback
    if r.status_code >= 400:
        logger.warning("[chatbot proxy] n8n status %s session=%s body=%s",
                       r.status_code, session_id, text[:500])
        return _fallback
    try:
        data = r.json()
    except ValueError:
        logger.info("[chatbot proxy] n8n devolvió texto plano session=%s elapsed=%sms",
                    session_id, elapsed_ms)
        return {"text": text, "qr_url": None, "pdf_url": None}
    if data is None:
        return _fallback
    logger.debug("[chatbot proxy] ok session=%s elapsed=%sms", session_id, elapsed_ms)
    return _normalize_chatbot_response(data)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errores = [
        {
            "campo": ".".join(str(loc) for loc in e["loc"][1:]),
            "detalle": e["msg"],
        }
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"ok": False, "mensaje": "Datos inválidos", "errores": errores},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "ok" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "mensaje": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no capturado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "mensaje": "Error interno del servidor"},
    )


@app.get("/_test_500")
def _test_500_endpoint():
    if os.environ.get("ENV") != "test":
        raise error("No disponible", 404)
    raise RuntimeError("Error deliberado de prueba")


# ── Startup ───────────────────────────────────────────────────────────────────

def open_browser():
    ngrok_url = os.environ.get("NGROK_URL", "").rstrip("/")
    url = f"{ngrok_url}/app" if ngrok_url else "http://localhost:8000/app"
    webbrowser.open(url)

if os.environ.get("TESTING") != "1" and os.environ.get("RAILWAY_ENVIRONMENT") is None:
    threading.Timer(1.5, open_browser).start()
