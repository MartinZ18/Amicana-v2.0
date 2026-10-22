"""Rate limiting en memoria por IP de cliente (ventana deslizante).

Vale para un solo proceso de uvicorn, que es como corre hoy (Railway, un
contenedor). Con varias réplicas cada una tendría su propio contador y
habría que moverlo a Redis.

Detrás del proxy de Railway, `request.client.host` es la IP del proxy. Con
TRUST_PROXY_XFF=1 (lo setea el Dockerfile) la IP del cliente es la última
entrada de X-Forwarded-For: la que agrega el proxy. Las de la izquierda las
puede inventar el cliente, por eso no se usa `--forwarded-allow-ips='*'` de
uvicorn, que se queda con la primera.
"""
import os
import threading
import time
from collections import deque

from fastapi import Request

from .responses import error


class SlidingWindowLimiter:
    """Permite `limit` eventos por clave dentro de `window` segundos."""

    def __init__(self, limit: int, window: float, max_keys: int = 10_000):
        self.limit = limit
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Registra un evento. Devuelve True si la clave ya agotó su cupo."""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                if len(self._hits) >= self.max_keys:
                    self._purge(cutoff)
                bucket = self._hits[key] = deque()
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return True
            bucket.append(now)
            return False

    def _purge(self, cutoff: float) -> None:
        """Descarta claves sin eventos recientes; si no alcanza, las más viejas."""
        for k in [k for k, b in self._hits.items() if not b or b[-1] <= cutoff]:
            del self._hits[k]
        overflow = len(self._hits) - self.max_keys + 1
        if overflow > 0:
            for k in sorted(self._hits, key=lambda k: self._hits[k][-1])[:overflow]:
                del self._hits[k]


def client_ip(request: Request) -> str:
    if os.environ.get("TRUST_PROXY_XFF") == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


_AUTH_LIMIT = int(os.environ.get("AUTH_RATE_LIMIT", "10"))
_AUTH_WINDOW = 60

login_limiter = SlidingWindowLimiter(_AUTH_LIMIT, _AUTH_WINDOW)
registro_limiter = SlidingWindowLimiter(_AUTH_LIMIT, _AUTH_WINDOW)


def limitar_login(request: Request) -> None:
    if login_limiter.hit(client_ip(request)):
        raise error("Demasiados intentos de inicio de sesión. Esperá un minuto.", 429)


def limitar_registro(request: Request) -> None:
    if registro_limiter.hit(client_ip(request)):
        raise error("Demasiados registros desde esta conexión. Esperá un minuto.", 429)
