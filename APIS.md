# APIs externas — AMICANA 2.0

Inventario de servicios externos integrados, con referencias de configuración.

---

## MercadoPago

**Propósito:** Procesamiento de pagos de cuotas por parte de los alumnos.  
**Flujo:** `POST /pagos/pagar-cuota/{id}` → crea preferencia MP → redirige al alumno → webhook `POST /pagos/webhook` actualiza el estado.

| Variable | Descripción |
|----------|-------------|
| `MP_ACCESS_TOKEN` | Token de la app MP. `TEST-...` = sandbox, `APP_USR-...` = producción |
| `MP_WEBHOOK_SECRET` | Clave para validar firma HMAC-SHA256 en webhooks. Si está vacío, se acepta sin validar |

**Obtener credenciales:** [mercadopago.com.ar/developers/panel](https://www.mercadopago.com.ar/developers/panel)  
**Endpoint webhook a registrar:** `https://<tu-dominio>/pagos/webhook`

---

## Google OAuth 2.0

**Propósito:** Login con cuenta de Google (alternativa a email/contraseña).  
**Flujo:** `GET /auth/google/login` → redirect a Google → callback `GET /auth/google/callback` → JWT local.

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Client ID de la app OAuth |
| `GOOGLE_CLIENT_SECRET` | Client Secret de la app OAuth |
| `GOOGLE_REDIRECT_URI` | URI de callback registrada en Google Console. Ej: `https://<dominio>/auth/google/callback` |
| `GOOGLE_POST_LOGIN_REDIRECT` | Página del frontend a la que redirigir con `?token=...` tras login exitoso |

**Obtener credenciales:** [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)  
**URI a registrar en Google Console:** `https://<tu-dominio>/auth/google/callback`

---

## n8n (Chatbot Ianna)

**Propósito:** Orquestación del chatbot. FastAPI hace de proxy: el widget JS llama a `POST /chatbot`, que reenvía a n8n, que consulta la BD o un LLM y devuelve la respuesta.

| Variable | Descripción |
|----------|-------------|
| `GROQ_API_KEY` | Clave del LLM del chatbot (Groq). La consume n8n vía `$env.GROQ_API_KEY` |
| `CHATBOT_INTERNAL_KEY` | Clave compartida entre FastAPI y n8n para autenticar llamadas internas |
| `N8N_WEBHOOK_URL` | URL del webhook de n8n. Default: `http://localhost:5678/webhook/amicana-chatbot` |
| `N8N_TIMEOUT_SECONDS` | Timeout en segundos para esperar respuesta de n8n. Default: `30` |
| `CHATBOT_RATE_LIMIT` | Máximo de mensajes por sesión por hora. Default: `30` |

**Workflow:** importar `n8n/amicana-chatbot.json` en la instancia n8n.  
**LLM por defecto:** Groq `llama-3.3-70b-versatile` vía endpoint OpenAI-compatible (`https://api.groq.com/openai/v1/chat/completions`). Gratis y sin tarjeta; obtener la key en [console.groq.com](https://console.groq.com). El proveedor es intercambiable editando el nodo **Groq Router** del workflow.

---

## ngrok (túnel de desarrollo)

**Propósito:** Exponer el backend local a internet para que MercadoPago y Google OAuth puedan enviar callbacks/webhooks durante el desarrollo.

| Variable | Descripción |
|----------|-------------|
| `NGROK_URL` | URL pública del túnel ngrok. Ej: `https://xxxx.ngrok-free.dev` |

**Nota:** En producción (Railway u otro proveedor) ngrok no es necesario, ya que el servidor tiene una URL pública propia.
