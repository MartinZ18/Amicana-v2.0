# AMICANA 2.0 — Sistema de Gestión

<p align="center">
  <a href="https://amicana-v20-production.up.railway.app/app/index.html">
    <img src="https://img.shields.io/badge/Live%20Demo-Online-brightgreen?style=for-the-badge&logo=railway&logoColor=white" />
  </a>
  <a href="https://amicana-v20-production.up.railway.app/docs">
    <img src="https://img.shields.io/badge/API%20Docs-Swagger-85EA2D?style=for-the-badge&logo=swagger&logoColor=black" />
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat&logo=mysql&logoColor=white" />
  <img src="https://img.shields.io/badge/MercadoPago-009EE3?style=flat&logo=mercadopago&logoColor=white" />
  <img src="https://img.shields.io/badge/Google%20OAuth-4285F4?style=flat&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/n8n-EA4B71?style=flat&logo=n8n&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Deployed%20on-Railway-0B0D0E?style=flat&logo=railway&logoColor=white" />
</p>

Sistema integral de administración académica para el Instituto Cultural Argentino Norteamericano (AMICANA). Cubre gestión de cuotas, pagos con MercadoPago, calendario académico, progreso del alumno y chatbot institucional.

**Stack:** Python 3.11 · FastAPI · MySQL 8 · Vanilla JS · Playwright · n8n

---

## Demo / Despliegue

🔗 **App:** https://amicana-v20-production.up.railway.app/app/index.html
🔗 **API docs (Swagger):** https://amicana-v20-production.up.railway.app/docs

| Email | Password | Rol |
|-------|----------|-----|
| `admin@amicana.com` | `admin1234` | admin |

---

## Índice

- [Demo / Despliegue](#demo--despliegue)
- [Requisitos](#requisitos)
- [Instalación desde cero](#instalación-desde-cero)
- [Orden de arranque diario](#orden-de-arranque-diario)
- [Variables de entorno](#variables-de-entorno)
- [Login inicial](#login-inicial)
- [Tests](#tests)
- [n8n — Chatbot Ianna](#n8n--chatbot-ianna-opcional)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Roles y accesos](#roles-y-accesos)
- [Documentación adicional](#documentación-adicional)

---

## Requisitos

| Herramienta | Versión mínima | Descarga |
|-------------|---------------|----------|
| Python | 3.11+ | [python.org](https://python.org) |
| MySQL | 8.0+ | [MySQL Community Server](https://dev.mysql.com/downloads/mysql/) o [XAMPP](https://apachefriends.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| ngrok | cualquiera | [ngrok.com/download](https://ngrok.com/download) |
| Git | cualquiera | [git-scm.com](https://git-scm.com) |

---

## Instalación desde cero

### 1. Clonar el repositorio

```bash
git clone https://github.com/MartinZ18/Amicana-v2.0.git
cd Amicana-v2.0
```

### 2. Base de datos

Iniciá MySQL. Luego creá la base de datos con el schema:

```bash
# Desde la raíz del proyecto
mysql -u root -p < database/BD_Amicana.sql
```

Esto crea la base `gestion_facturas_amicana` con todas las tablas y datos iniciales.

Verificación rápida:

```sql
USE gestion_facturas_amicana;
SHOW TABLES;
```

> **Puerto**: MySQL Server estándar usa el puerto **3306**. XAMPP puede usar **3307**. Confirmá el tuyo antes de configurar el `.env`.

> **¿Ya tenés datos viejos?** No uses `BD_Amicana.sql`. Aplicá solo las migraciones nuevas desde `database/migrations/` en orden numérico. Ver [`database/README.md`](database/README.md).

### 3. Variables de entorno

```bash
cp backend/.env.example backend/.env
```

Abrí `backend/.env` y completá:

**a) Generá una SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copiá el resultado en `SECRET_KEY=`.

**b) Completá las credenciales de MySQL** (`DB_PASSWORD`, y `DB_PORT` si no es 3306).

**c) Las demás variables** (MercadoPago, Google OAuth, Groq para el chatbot) son opcionales según las funcionalidades que quieras usar. Ver la sección [Variables de entorno](#variables-de-entorno) para el detalle.

### 4. Entorno virtual Python

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 5. Dependencias de testing (Playwright)

```bash
# Desde la raíz del proyecto
cd ..
npm install
npx playwright install chromium
```

### 6. ngrok (necesario para Google OAuth y webhooks de MercadoPago)

ngrok expone el backend local a internet. Sin él, Google OAuth y MercadoPago no pueden comunicarse con tu máquina.

```bash
# 1. Crear cuenta gratuita en ngrok.com y copiar el authtoken
ngrok config add-authtoken <TU_AUTHTOKEN>

# 2. Levantar el túnel (necesita el backend corriendo en el puerto 8000)
ngrok http 8000
```

ngrok te da una URL temporal como `https://xxxx-xxx.ngrok-free.dev`. Copiala y:

- Poné esa URL en `NGROK_URL=` en `backend/.env`.
- Actualizá `GOOGLE_REDIRECT_URI=https://xxxx-xxx.ngrok-free.dev/auth/google/callback` en `backend/.env`.
- Registrá esa misma URI en [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → tu OAuth Client → Authorized redirect URIs.
- Registrá `https://xxxx-xxx.ngrok-free.dev/pagos/webhook` en MercadoPago si usás pagos.

> **Dominio estático (opcional):** ngrok permite reservar un dominio fijo para que no cambie en cada reinicio. Ver `ngrok.com/docs` → Static Domains.

### 7. Google OAuth (si vas a usar login con Google)

1. Ir a [console.cloud.google.com](https://console.cloud.google.com/apis/credentials).
2. Crear un proyecto (o usar uno existente).
3. Habilitar la **Google+ API** / **Google Identity**.
4. Crear credenciales → **OAuth client ID** → tipo **Web application**.
5. En **Authorized redirect URIs** agregar:
   - `http://localhost:8000/auth/google/callback` (para pruebas locales sin ngrok)
   - `https://<tu-dominio-ngrok>/auth/google/callback` (para pruebas con ngrok)
6. Copiar el `Client ID` y `Client Secret` en `backend/.env`.

---

## Orden de arranque diario

Seguí este orden exacto cada vez que levantés el proyecto:

**Paso 1 — MySQL**
```
XAMPP → Start MySQL
```
o si usás MySQL Server, verificá que esté corriendo.

**Paso 2 — Backend** (Terminal A, desde la carpeta `backend/`)
```bash
venv\Scripts\activate
uvicorn app.main:app --reload
```
Esperá a ver `Application startup complete`.

**Paso 3 — ngrok** (Terminal B, solo si usás Google OAuth o MercadoPago)
```bash
ngrok http 8000
```
Esperá a ver `Forwarding ... https://...ngrok-free.dev`.

**Paso 4 — Abrir la app**
```
http://localhost:8000/app/index.html
```

> También podés usar el script `iniciar.bat` (Windows) desde la raíz del proyecto para los pasos 1 y 2.

> Los tests de Playwright no necesitan ngrok; se conectan directo a `localhost:8000`.

---

## Variables de entorno

Copiá `backend/.env.example` a `backend/.env` y completá los valores.

### Obligatorias (la app no arranca sin estas)

| Variable | Descripción |
|----------|-------------|
| `DB_HOST` | Host de MySQL. Normalmente `localhost` |
| `DB_PORT` | Puerto de MySQL. **3306** para MySQL Server estándar, **3307** para XAMPP en algunos sistemas |
| `DB_USER` | Usuario MySQL. Normalmente `root` |
| `DB_PASSWORD` | Password de tu instalación MySQL |
| `DB_NAME` | Nombre de la BD. Dejar `gestion_facturas_amicana` |
| `SECRET_KEY` | Clave para firmar JWT. Generar con: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_SEED_PASSWORD` | Password del usuario `admin@amicana.com` creado automáticamente al primer arranque |

### Opcionales según features

| Variable | Feature | Notas |
|----------|---------|-------|
| `GROQ_API_KEY` | LLM del chatbot Ianna (vía n8n) | Gratis sin tarjeta — obtener en [console.groq.com](https://console.groq.com). Modelo `llama-3.3-70b-versatile` |
| `MP_ACCESS_TOKEN` | Pagos con MercadoPago | Usar `TEST-...` para sandbox, `APP_USR-...` para producción |
| `MP_WEBHOOK_SECRET` | Validación de firma en webhooks MP | Si está vacío, los webhooks se aceptan sin validar firma |
| `GOOGLE_CLIENT_ID` | Login con Google | Ver paso 7 de instalación |
| `GOOGLE_CLIENT_SECRET` | Login con Google | Ver paso 7 de instalación |
| `GOOGLE_REDIRECT_URI` | Login con Google | Debe coincidir exactamente con lo registrado en Google Console |
| `GOOGLE_POST_LOGIN_REDIRECT` | Login con Google | URL del frontend tras login exitoso. Default: `http://localhost:8000/app/index.html` |
| `NGROK_URL` | URL pública del backend | Solo necesaria si usás MP webhooks o Google OAuth con ngrok |
| `CHATBOT_INTERNAL_KEY` | Autenticación entre n8n y el backend | Debe coincidir con la variable en n8n |
| `N8N_WEBHOOK_URL` | URL del webhook de n8n | Default: `http://localhost:5678/webhook/amicana-chatbot` |
| `CORS_ORIGINS` | Orígenes CORS permitidos | CSV de URLs. Vacío = solo localhost. En producción definir explícitamente |

---

## Login inicial

| Email | Password | Rol |
|-------|----------|-----|
| `admin@amicana.com` | El valor de `ADMIN_SEED_PASSWORD` en `.env` | admin |

El admin se crea automáticamente al primer arranque si no existe en la BD.

La API docs interactiva está en: `http://localhost:8000/docs`

---

## Tests

### Unitarios (pytest)

```bash
cd backend
pip install -r requirements-dev.txt   # incluye pytest (solo la primera vez)
pytest tests/ -v
```

No necesitan MySQL ni credenciales: la suite mockea la base de datos y `conftest.py`
inyecta los valores de entorno necesarios.

### Smoke check rápido (sin BD)

```bash
cd backend
python -c "from app.main import app; print('OK — rutas:', len(app.routes))"
```

### UI y API (Playwright)

**Requisito:** el backend debe estar corriendo en `localhost:8000` con la BD activa.

```bash
# Desde la raíz del proyecto

# Actividad 1 — UI funcional
npx playwright test --project=actividad-01-ui

# Actividad 2 — API + mocking + híbrido
npx playwright test --project=actividad-02-api-mock

# Actividad 3 — Regresion
npx playwright test --project=actividad-03-regresion

# Todos los tests
npx playwright test

# Ver reporte HTML con screenshots
npx playwright show-report
```

Ver [`tests/README.md`](tests/README.md) para más detalle.

---

## n8n — Chatbot Ianna (opcional)

Si querés probar el chatbot localmente:

```bash
# Desde la raíz del proyecto
docker compose up -d
```

n8n quedará disponible en `http://localhost:5678`.

Para importar el workflow:
1. Abrir `http://localhost:5678`.
2. Ir a **Workflows** → botón de importar.
3. Seleccionar el archivo `n8n/amicana-chatbot.json`.
4. Configurar la variable `CHATBOT_INTERNAL_KEY` en n8n Settings > Variables con el mismo valor que en `backend/.env`.

---

## Estructura del proyecto

```
<tu-repo>/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI: lifespan, CORS, routers, seed admin
│   │   ├── auth.py              ← JWT, bcrypt, dependencias de auth
│   │   ├── database.py          ← Conexión MySQL desde variables de entorno
│   │   ├── dependencies.py      ← get_current_user (inyección de dependencias)
│   │   ├── schemas/             ← Modelos Pydantic por dominio
│   │   ├── routers/             ← auth, google_auth, alumnos, cursos, pagos,
│   │   │                          perfil, avisos, calendario, eventos,
│   │   │                          comunicados, reportes, configuracion,
│   │   │                          progreso, chatbot, chatbot_data, qr
│   │   ├── services/            ← google, mercadopago, pdf, auditoria
│   │   └── utils/               ← responses, validators
│   ├── tests/                   ← Tests de integración (pytest)
│   ├── requirements.txt
│   ├── .env.example             ← Plantilla de configuración (copiar a .env)
│   └── pytest.ini
├── database/
│   ├── BD_Amicana.sql           ← Schema canónico — usar para instalación nueva
│   ├── migrations/              ← Migraciones incrementales (solo para upgrades)
│   └── README.md
├── frontend/
│   ├── index.html               ← Login / Registro / Google OAuth
│   ├── admin.html               ← Panel administrativo completo
│   ├── alumno.html              ← Portal del alumno
│   └── estilos.css
├── static/
│   └── chatbot-widget.js        ← Widget del chatbot Ianna
├── n8n/
│   └── amicana-chatbot.json     ← Workflow del chatbot (importar en n8n)
├── tests/
│   ├── actividad-01-ui/         ← Tests de UI funcional (Playwright)
│   ├── actividad-02-api-mock/   ← Tests de API + mocking + híbrido
│   └── README.md
├── docs/
│   └── specs/                   ← Especificaciones por release
├── docker-compose.yml           ← n8n local
├── playwright.config.js
├── package.json
├── iniciar.bat                  ← Script de arranque Windows
├── APIS.md                      ← Inventario de APIs externas
├── CHANGELOG.md                 ← Historial de cambios
└── README.md
```

---

## Roles y accesos

| Rol | Permisos |
|-----|----------|
| `admin` | Acceso total: cuotas, alumnos, cursos, pagos, eventos, reportes, configuración, auditoría |
| `administrativo` | Igual que admin, sin módulo de auditoría |
| `alumno` | Sus cuotas, pagar, chatbot, progreso, calendario |

---

## Documentación adicional

| Archivo | Contenido |
|---------|-----------|
| [`docs/documentacion_tecnica.md`](docs/documentacion_tecnica.md) | Arquitectura, módulos, modelo de datos, seguridad y decisiones técnicas |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de releases por etapa |
| [`APIS.md`](APIS.md) | Inventario de APIs externas y configuración |
| [`GUIA_USUARIO.md`](GUIA_USUARIO.md) | Guía de uso por rol (alumno / admin) |
| [`DEPLOY.md`](DEPLOY.md) | Despliegue en Railway paso a paso |
| [`database/README.md`](database/README.md) | Instalación y upgrade de la base de datos |
| [`tests/README.md`](tests/README.md) | Guía completa de testing con Playwright |
| [`tests/actividad-03-regresion/INFORME.md`](tests/actividad-03-regresion/INFORME.md) | Reporte de pruebas de regresión (28 casos, CRUD/auth/validaciones/API externa) |

---

## Equipo

**Martín Zamora** — martin.zamora004@gmail.com
**Luciano Papagni** — lucianopapagni123@gmail.com
**Milton Rivera** — ballafd@gmail.com
**Franco Prolongo** — franklinelcrack3@gmail.com
**Diego Toconas** — dtoconas78@gmail.com

