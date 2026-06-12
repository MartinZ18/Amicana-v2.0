FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crea la carpeta de facturas por si el .gitkeep no se copió
RUN mkdir -p backend/static/facturas static

EXPOSE 8000

# Exec form + sh -c para expandir $PORT de Railway y recibir señales SIGTERM
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
