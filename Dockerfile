FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crea la carpeta de facturas por si el .gitkeep no se copió
RUN mkdir -p backend/static/facturas static

EXPOSE 8000

# Exec form + sh -c para expandir $PORT de Railway y recibir señales SIGTERM.
# TRUST_PROXY_XFF: el contenedor solo recibe tráfico a través del proxy de
# Railway; el rate limiting toma la IP real de la entrada que ese proxy agrega
# al final de X-Forwarded-For (ver backend/app/rate_limit.py).
ENV TRUST_PROXY_XFF=1
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
