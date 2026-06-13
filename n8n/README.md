# n8n — Workflow Ianna Chatbot

## Importar el workflow

1. Abrí n8n en `http://localhost:5678`.
2. Menú → **Workflows** → **Import from file**.
3. Seleccioná `n8n/amicana-chatbot.json`.
4. Activá el workflow (toggle en la esquina superior derecha).

## Variables de entorno requeridas

Estas variables se cargan en n8n desde `backend/.env` (el `docker-compose.yml` las pasa con `env_file`) y el workflow las lee con `{{ $env.NOMBRE }}` (requiere `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`, ya seteado en el compose):

| Variable | Descripción | Ejemplo |
|---|---|---|
| `GROQ_API_KEY` | Clave del LLM (Groq, gratis sin tarjeta — console.groq.com) | `gsk_...` |
| `FASTAPI_BASE_URL` | URL pública del backend FastAPI, **sin slash final** (usada por todos los nodos HTTP del workflow) | `https://tu-backend.up.railway.app` |
| `CHATBOT_INTERNAL_KEY` | Clave inter-servicio (`X-Chatbot-Key`), debe coincidir con la del backend | `amicana-internal` |

> El LLM lo resuelve el nodo HTTP **Groq Router** (`https://api.groq.com/openai/v1/chat/completions`, modelo `llama-3.3-70b-versatile`, formato OpenAI). La key viaja en el header `Authorization: Bearer {{ $env.GROQ_API_KEY }}`.
>
> **Tras cambiar `backend/.env`**: recrear el contenedor con `docker compose up -d --force-recreate n8n` (un `restart` no relee `env_file`) y reimportar el workflow.

## Flujo del workflow

```
Webhook (POST /webhook/amicana-chatbot)
  │
  ├─ Pre-Auth Check: ¿viene user_token (JWT)?
  │    ├─ Sí → decodifica JWT → salta AUTH flow → usa alumno_id directo
  │    └─ No → continúa con flujo AUTH normal
  │
  ├─ GET /chatbot/session/{session_id}  → recupera estado
  │
  ├─ Router de intents (LLM / Switch):
  │    ├─ AUTH       → pide DNI → POST /chatbot/identificar-alumno
  │    ├─ ESTADO     → GET /chatbot/alumno/{id}/estado-cuotas
  │    ├─ PAGAR      → POST /pagar-cuota/{cuota_id}
  │    ├─ CONFIRMAR  → POST /pagos/confirmar-manual
  │    ├─ PDF        → POST /pagos/generar-factura-pdf
  │    ├─ FUERA_SCOPE→ respuesta estándar de fuera de alcance
  │    └─ CERRAR     → despedida
  │
  └─ POST /chatbot/session → guarda estado actualizado
       │
       └─ Respond to Webhook → {text, qr_url?, pdf_url?}
```

## Cron de limpieza (5.8)

Agrega un nodo **Schedule Trigger** (cada día a las 03:00) que llame a:

```
DELETE /chatbot/sessions/stale?days=30
Authorization: Bearer <JWT admin>
```

O configuralo en el workflow como nodo `HTTP Request` separado.

## Nodo "Respond to Webhook" — formato de respuesta

Siempre devolver JSON con esta forma (el proxy FastAPI también normaliza):

```json
{
  "text": "Respuesta visible al usuario",
  "qr_url": null,
  "pdf_url": null
}
```

Si hay QR o PDF, incluirlos como URLs absolutas o relativas al backend.

## Actualizar el workflow

1. Modificar en n8n.
2. Exportar: menú 3 puntos → **Download**.
3. Reemplazar `n8n/amicana-chatbot.json` con el archivo descargado.
4. Commitear.
