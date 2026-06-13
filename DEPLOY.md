# Guía de despliegue en Railway

Railway permite desplegar el backend FastAPI + MySQL en la nube de forma gratuita (crédito de $5/mes incluido).

---

## Requisitos previos

- Cuenta en [railway.app](https://railway.app) (gratis, sin tarjeta para empezar)
- Repositorio en GitHub con el código fuente
- Archivo `backend/.env.example` como referencia para las variables

---

## Paso 1 — Crear el proyecto en Railway

1. Ingresá a [railway.app](https://railway.app) y hacé clic en **New Project**.
2. Seleccioná **Deploy from GitHub repo**.
3. Autorizá Railway para acceder a tu GitHub y seleccioná el repositorio recién creado.
4. Railway detecta automáticamente la configuración de `railway.toml` (que indica buildear con el `Dockerfile`).

---

## Paso 2 — Agregar MySQL

1. Dentro del proyecto, hacé clic en **+ New** → **Database** → **Add MySQL**.
2. Railway crea una instancia MySQL y te da las variables de conexión automáticamente:
   - `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`

---

## Paso 3 — Configurar variables de entorno

En el servicio de FastAPI (no en MySQL), hacé clic en **Variables** y agregá:

### Obligatorias

| Variable | Valor |
|----------|-------|
| `DB_HOST` | Copiar de `${{MySQL.MYSQLHOST}}` (Railway lo inyecta automáticamente) |
| `DB_PORT` | Copiar de `${{MySQL.MYSQLPORT}}` |
| `DB_USER` | Copiar de `${{MySQL.MYSQLUSER}}` |
| `DB_PASSWORD` | Copiar de `${{MySQL.MYSQLPASSWORD}}` |
| `DB_NAME` | `gestion_facturas_amicana` |
| `SECRET_KEY` | Generá con: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_SEED_PASSWORD` | Password para el admin inicial (elegí una contraseña segura) |

> **Tip Railway:** En lugar de copiar los valores, podés usar referencias directas: en el campo valor escribí `${{MySQL.MYSQLHOST}}` y Railway lo resuelve automáticamente.

### Opcionales (según features que quieras en producción)

| Variable | Feature |
|----------|---------|
| `MP_ACCESS_TOKEN` | Pagos MercadoPago |
| `MP_WEBHOOK_SECRET` | Validación de webhooks MP |
| `GOOGLE_CLIENT_ID` | Login con Google |
| `GOOGLE_CLIENT_SECRET` | Login con Google |
| `GOOGLE_REDIRECT_URI` | Login con Google — usar la URL pública de Railway |
| `GOOGLE_POST_LOGIN_REDIRECT` | URL del frontend tras login Google |
| `CORS_ORIGINS` | Orígenes CORS permitidos (usar URL pública de Railway) |
| `N8N_WEBHOOK_URL` | Chatbot Ianna — URL del webhook de n8n. Ver Paso 8 |
| `CHATBOT_INTERNAL_KEY` | Chatbot Ianna — clave compartida con n8n. Ver Paso 8 |

---

## Paso 4 — Inicializar la base de datos

Una vez que el servicio MySQL esté corriendo, cargás el schema **con un solo
archivo**: `database/BD_Amicana.sql` ya consolida las 14 migraciones (001→012)
y es idempotente (`CREATE TABLE IF NOT EXISTS`). **No** corras las migraciones
una por una — solo sirven para actualizar una BD que ya tiene datos.

> ⚠️ **Nombre de la BD:** `BD_Amicana.sql` hace `CREATE DATABASE ... gestion_facturas_amicana`
> y `USE gestion_facturas_amicana`. Por eso en las variables (Paso 3) tiene que ir
> `DB_NAME=gestion_facturas_amicana` — **no** el `railway` que Railway crea por
> defecto. El usuario root que da Railway tiene permiso para crear esa BD.

**Opción A — Desde Railway CLI (recomendado):**
```bash
npm install -g @railway/cli
railway login
railway link            # elegí el proyecto
railway connect MySQL    # abre una sesión mysql; pegá el contenido de BD_Amicana.sql
```

**Opción B — Cliente MySQL externo:**
1. En Railway → servicio MySQL → **Connect** → copiá las credenciales de conexión externa.
2. Conectate con TablePlus, DBeaver o MySQL Workbench usando esas credenciales.
3. Ejecutá `database/BD_Amicana.sql` completo. Listo — no hace falta nada más.

---

## Paso 5 — Primer deploy

1. Railway detecta el push a la rama principal y hace el build automáticamente.
2. En **Deployments** podés ver los logs en tiempo real.
3. Una vez que aparezca `Application startup complete`, el sistema está listo.
4. Hacé clic en **Settings** → **Domains** → **Generate Domain** para obtener la URL pública.

La URL tendrá el formato: `https://<nombre-del-servicio>-production.up.railway.app`

---

## Paso 6 — Actualizar URLs en servicios externos

Con la URL pública de Railway, actualizá:

1. **Google Console** → tu OAuth Client → Authorized redirect URIs → agregar `https://<tu-url-railway>/auth/google/callback`
2. **MercadoPago** → Developers → tu app → Webhooks → URL: `https://<tu-url-railway>/pagos/webhook`
3. En Railway variables: `GOOGLE_REDIRECT_URI`, `CORS_ORIGINS`, `GOOGLE_POST_LOGIN_REDIRECT`

---

## Paso 7 — Verificar el deploy

```bash
# Smoke check
curl https://<tu-url-railway>/Prueba
# Respuesta esperada: {"mensaje":"AMICANA 2.0 funcionando 🔥"}

# Login admin
curl -X POST https://<tu-url-railway>/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@amicana.com","password":"<ADMIN_SEED_PASSWORD>"}'
```

---

## Paso 8 — Desplegar n8n (Chatbot Ianna)

El chatbot Ianna necesita una instancia de n8n corriendo y accesible públicamente:
el backend hace un POST a `N8N_WEBHOOK_URL` por cada mensaje. La forma más simple
es desplegar n8n como **otro servicio dentro del mismo proyecto Railway**.

### 8.1 — Crear el servicio

1. En el proyecto Railway (el mismo que tiene el backend y MySQL), hacé clic en
   **+ New** → **Empty Service**.
2. **Settings → Source** → **Deploy from Docker Image** → `n8nio/n8n:latest`.

### 8.2 — Variables de entorno del servicio n8n

| Variable | Valor |
|----------|-------|
| `N8N_HOST` | dominio público que le asignes a este servicio (sin `https://`), ej. `amicana-n8n.up.railway.app` |
| `N8N_PROTOCOL` | `https` |
| `N8N_PORT` | `5678` |
| `WEBHOOK_URL` | `https://<mismo-dominio>/` (con `/` al final) |
| `GENERIC_TIMEZONE` | `America/Argentina/Buenos_Aires` |
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | `false` |
| `N8N_BLOCK_ENV_ACCESS_IN_NODE` | `false` (el workflow lee `GROQ_API_KEY`, `FASTAPI_BASE_URL` y `CHATBOT_INTERNAL_KEY` vía `$env`) |
| `GROQ_API_KEY` | tu API key de [console.groq.com](https://console.groq.com) |
| `CHATBOT_INTERNAL_KEY` | la misma clave que vas a poner en el backend (ver 8.6) |
| `FASTAPI_BASE_URL` | URL pública del backend FastAPI desplegado en los pasos 1-5, **sin slash final** (ej. `https://tu-backend.up.railway.app`). Todos los nodos HTTP del workflow la usan para llamar al backend |

### 8.3 — Volumen para persistencia

Sin un volumen, n8n pierde los workflows importados en cada redeploy.

1. Servicio n8n → **Settings → Volumes** → **+ New Volume**.
2. Mount path: `/home/node/.n8n`.

### 8.4 — Generar dominio público

**Settings → Networking → Generate Domain**. n8n escucha en el puerto `5678`
(`N8N_PORT`) — asegurate que **Target Port** sea `5678`.

Anotá la URL generada, la necesitás en el paso 8.6.

### 8.5 — Importar el workflow

1. Abrí `https://<tu-dominio-n8n>` y completá el setup inicial (usuario admin).
2. **Workflows → Import from File** → seleccioná `n8n/amicana-chatbot.json`.
3. Activá el workflow (toggle **Active**).

### 8.6 — Conectar el backend con n8n

En el servicio **backend** (Variables), agregá:

| Variable | Valor |
|----------|-------|
| `N8N_WEBHOOK_URL` | `https://<tu-dominio-n8n>/webhook/amicana-chatbot` |
| `CHATBOT_INTERNAL_KEY` | la misma clave del paso 8.2 |

Railway redeploya el backend automáticamente al guardar las variables.

### 8.7 — Verificar

Abrí el frontend (`https://<tu-url-railway>/app`), iniciá sesión y probá el
widget del chatbot Ianna. Si responde "El asistente no está disponible", revisá:
- Que el workflow esté **Active** en n8n.
- Que `CHATBOT_INTERNAL_KEY` coincida en ambos servicios.
- Logs del servicio n8n en Railway.

---

## CI/CD con GitHub Actions

El repo incluye `.github/workflows/deploy.yml`. En cada push y PR a `main` corre
la suite de tests; si pasan **y** el push fue a `main`, despliega el backend a
Railway con la CLI (`railway up`, que buildea con el `Dockerfile`).

```
push/PR a main ─▶ job test (pytest) ─▶ [solo push a main] job deploy (railway up)
```

### Configuración (una sola vez)

1. **Project token de Railway**
   Railway → tu proyecto → **Settings → Tokens → Create Token**. Copiá el valor.

2. **Cargar el token en GitHub**
   Repo → **Settings → Secrets and variables → Actions**:
   - Pestaña **Secrets** → **New repository secret**
     - Name: `RAILWAY_TOKEN` — Value: el token del paso 1
   - Pestaña **Variables** → **New repository variable** (opcional)
     - Name: `RAILWAY_SERVICE` — Value: el nombre exacto del servicio backend en
       Railway (si no la definís, el workflow usa `amicana-backend`).

3. **Listo.** El próximo push a `main` corre tests y, si pasan, deploya.
   El deploy también se puede lanzar a mano desde la pestaña **Actions → CI/CD →
   Run workflow** (`workflow_dispatch`).

> El servicio MySQL y, si lo usás, n8n se aprovisionan una sola vez en el panel
> de Railway (no se buildean desde este repo). El pipeline redeploya solo el
> backend FastAPI. La inicialización del schema (Paso 4) también es manual la
> primera vez.

> **Nota:** desactivá el auto-deploy nativo de Railway (servicio → Settings →
> **Source / Deploy Triggers**) para que el deploy lo maneje solo GitHub Actions
> y no se dispare dos veces por cada push.

### Tests E2E (Playwright)

No corren en el pipeline porque necesitan el stack completo arriba (MySQL +
servidor + navegador). Se ejecutan localmente con `npx playwright test` contra
`http://localhost:8000`.

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| Build falla con `ModuleNotFoundError` | Falta dependencia en `requirements.txt` | Agregar el paquete y hacer push |
| `Can't connect to MySQL` | Variables DB mal configuradas | Verificar `DB_HOST`, `DB_PORT`, `DB_PASSWORD` en Railway variables |
| `Table 'x' doesn't exist` | Schema no cargado | Ejecutar `BD_Amicana.sql` + migraciones contra el MySQL de Railway |
| OAuth redirige a URL incorrecta | `GOOGLE_REDIRECT_URI` desactualizada | Actualizar la variable con la URL pública de Railway |
| CORS error en el frontend | `CORS_ORIGINS` no incluye la URL de Railway | Agregar la URL pública a `CORS_ORIGINS` |
| Chatbot responde "no disponible" | n8n no desplegado, workflow inactivo, o `N8N_WEBHOOK_URL`/`CHATBOT_INTERNAL_KEY` mal configurados | Ver Paso 8 — verificar que el workflow esté Active y que las claves coincidan en ambos servicios |
