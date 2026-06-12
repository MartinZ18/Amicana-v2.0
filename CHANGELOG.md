# Changelog — AMICANA 2.0

## [Sin publicar]

### Agregado
- `DEPLOY.md`: paso a paso para desplegar n8n (chatbot Ianna) como servicio
  adicional en Railway, con volumen persistente y conexión al backend vía
  `N8N_WEBHOOK_URL` / `CHATBOT_INTERNAL_KEY`.

### Cambiado
- **Chatbot Ianna: LLM migrado de Gemini a Groq** (`llama-3.3-70b-versatile`, API OpenAI-compatible). El free tier de Gemini quedó en `limit: 0` por región y habilitar billing requería un pago no disponible; Groq es gratis y sin tarjeta.
  - Workflow n8n (`n8n/amicana-chatbot.json`): nodo `Gemini Router` → `Groq Router`; `Hydrate Session` ahora arma los `messages` en formato OpenAI; `Parse Intent` lee `choices[0].message.content`.
  - Nueva variable `GROQ_API_KEY` en `backend/.env` (la consume n8n vía `env_file` del `docker-compose.yml`).

### Corregido
- El chatbot caía siempre al mensaje genérico (FUERA_SCOPE) porque el LLM devolvía `429 quota exceeded` (`limit: 0`).

### Eliminado
- `nixpacks.toml` — config muerta: `railway.toml` ya fija `builder = "DOCKERFILE"`
  y Railway lo ignoraba por completo.
- Restos del módulo de **OCR de facturas** (ya removido del código activo): dependencia `google-genai` de `requirements.txt`, variable `GEMINI_API_KEY` (`.env`, `.env.example` y boilerplate de tests), imágenes huérfanas en `uploads/` y bytecode stale de `gemini_ocr`/`ollama_ocr`/`facturas`. Se documentó en README, APIS.md, DEPLOY.md y CLAUDE.md. `Pillow` se conserva (lo usa la generación de QR de pagos).

---

## v2.5 — Etapa 5: Release Candidate (2026-06-09)

### Agregado
- Suite de regresión Playwright (28 tests, 8 funcionalidades críticas) — `tests/actividad-03-regresion/`
- Informe de regresión con tabla de diseño y cobertura completa
- Configuración de despliegue en Railway (`railway.toml`, `nixpacks.toml`)
- Script de arranque Windows `iniciar.bat`
- Documentación de despliegue `DEPLOY.md`
- Inventario de APIs externas `APIS.md`
- Guía de usuario `GUIA_USUARIO.md`

### Corregido
- Prevención de apertura de browser en entorno Railway (`RAILWAY_ENVIRONMENT`)

---

## v2.4 — Etapa 4: Integraciones y Correcciones (2026-05-06)

### Agregado
- Tests Playwright: Actividad 1 (UI, 6 tests) y Actividad 2 (API + mocking + híbrido, 29 tests)
- Módulo de progreso del alumno (`routers/progreso.py`, migración 012)
- Módulo de notas por unidad (`migrations/012_notas_unidades.sql`)
- Completar perfil obligatorio tras login con Google OAuth
- Filtros de cursos por modalidad y categoría en el panel admin

### Corregido
- Bug: `JSON.stringify()` con comillas dobles rompía atributos `onclick` en filtros de cursos
- Bug: botón `btn-logout` en `alumno.html` no tenía `data-testid`, causaba timeout en tests
- Bug: credenciales MySQL incorrectas (`DB_PASSWORD`) — documentadas en `.env.example`

---

## v2.3 — Etapa 3: Panel Admin y Chatbot (2025-11-01)

### Agregado
- Rediseño completo del panel administrativo (`admin.html`): 6 módulos con filtros
- Eventos institucionales (`routers/eventos.py`, migración 010)
- Configuración del instituto (`routers/configuracion.py`, migración 011)
- Reportes de deudores con exportación PDF (`routers/reportes.py`)
- Chatbot Ianna: widget Vanilla JS + proxy FastAPI + workflow n8n (`n8n/amicana-chatbot.json`)
- Modal de bienvenida y FAQ para el chatbot (`routers/chatbot_data.py`)
- Rate limiting del chatbot por sesión (`CHATBOT_RATE_LIMIT`)
- Módulo de avisos institucionales (`routers/avisos.py`, migración 007)
- Módulo de comunicados (`routers/comunicados.py`)
- Calendario académico (`routers/calendario.py`, migración 008)
- Panel del alumno rediseñado: Mi Progreso, Calendario, Quiénes Somos

### Corregido
- Reorganización completa en arquitectura de routers/services/schemas
- Separación `pagos` (genérico) vs `pagos_mp` (MercadoPago)

---

## v2.2 — Etapa 2: Auth Dual y MercadoPago (2025-09-01)

### Agregado
- Login con Google OAuth 2.0 (`routers/google_auth.py`, migración 006)
- Endpoint `/perfil` GET/PUT con seteo de password local
- Integración MercadoPago Checkout Pro: preferencias, webhooks, verificación
- Generación de QR bancario sin comisión (`qr_generator.py`)
- Generación de PDF de recibo (`services/pdf_service.py`)
- Página de Términos y Condiciones (`frontend/terms.html`)
- Endpoint `DELETE /alumnos/{id}` con auditoría

### Corregido
- Normalización de email a minúsculas en registro y búsqueda
- Validación de password mínimo (8 chars, letra + número)

---

## v2.1 — Etapa 1: Base del Sistema (2025-07-01)

### Agregado
- Proyecto FastAPI con autenticación JWT (python-jose + bcrypt)
- Tres roles: `admin`, `administrativo`, `alumno`
- CRUD de alumnos, cursos y cuotas
- Seed automático del usuario admin al iniciar
- Frontend: `index.html` (login/registro), `admin.html`, `alumno.html`
- Schema de base de datos MySQL (`database/BD_Amicana.sql`)
- OCR de facturas con Google Gemini (`gemini_ocr.py`)
- Módulo de auditoría (`services/auditoria_service.py`)
- Tests pytest para rutas principales
