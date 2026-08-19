# RAG del chatbot Ianna — setup

Reemplaza el conocimiento hardcodeado de la rama `FUERA_SCOPE` del chatbot por retrieval
real sobre datos que ya existen en Amicana (`/chatbot/faq`, `/chatbot/cursos/info`,
`/chatbot/avisos`). Stack 100% free tier: Groq (LLM) + Google Gemini
(`text-embedding-004`, embeddings, 768 dims) + Supabase Postgres/pgvector (vector store).

## Estado actual

Los dos workflows ya están cargados en la instancia n8n (`https://n8n.martinzn8n.dpdns.org`),
ambos **inactivos** hasta completar este setup:

| Workflow | ID |
|---|---|
| AMICANA RAG — Ingesta (FAQ + Cursos + Avisos) | `VynboXqhM7BeV4NH` |
| AMICANA Chatbot — Cuotas (Groq) | `IC9CSDkcD10pSScd` |

## 1. Supabase

1. Crear proyecto en supabase.com (free tier, 500MB).
2. SQL Editor → pegar y correr `supabase-setup.sql` (está en esta misma carpeta).
3. Settings → API: copiar `Project URL` y la key `service_role` (no la `anon` — la
   ingesta necesita permiso de escritura).

## 2. Variables de entorno de n8n

La instancia es n8n community, así que **Settings → Variables no está disponible**
(es una feature de pago). Las variables se inyectan como env vars del contenedor:
ya están declaradas en `C:\n8n\docker-compose.yml` y sus valores viven en `C:\n8n\.env`.

| Variable | Valor |
|---|---|
| `AMICANA_API_URL` | URL base del backend. Con uvicorn local: `http://host.docker.internal:8000` |
| `CHATBOT_INTERNAL_KEY` | `amicana-internal` (default de `backend/app/auth.py`) |
| `GROQ_API_KEY` | console.groq.com/keys |
| `GEMINI_API_KEY` | aistudio.google.com/apikey |
| `SUPABASE_URL` | `https://<project>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | del paso 1.3 |

Después de completar `C:\n8n\.env`, aplicar con:

```
cd C:\n8n
docker compose up -d
```

## 3. Backend accesible

Los workflows apuntan a `$env.AMICANA_API_URL` — no a un dominio fijo. El deploy de
Railway que estaba hardcodeado (`proyecto-amicana-20-production.up.railway.app`) ya no
existe: responde `Application not found`. Hay que apuntar `AMICANA_API_URL` a un backend
vivo, sea local (`uvicorn backend.app.main:app --reload` + `http://host.docker.internal:8000`)
o a un deploy nuevo.

## 4. Ingesta

Abrir "AMICANA RAG — Ingesta" en n8n → **Execute workflow**. Puebla `documents` con FAQ +
cursos + avisos. Es idempotente (upsert por `source, external_id`), se puede re-correr
cada vez que se agreguen avisos o cursos nuevos. El nodo devuelve
`{ upserted, total, errors }` — si `errors` no está vacío, ahí está el detalle.

## 5. Verificar

1. En Supabase: `select count(*) from documents;` debe dar > 0.
2. Activar el workflow del chatbot y mandarle una pregunta fuera del scope de cuotas:

```
curl -X POST https://hook.martinzn8n.dpdns.org/webhook/amicana-chatbot \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"test-rag-1\",\"message\":\"que examenes puedo rendir?\"}"
```

La respuesta tiene que citar contenido real de `/chatbot/faq`, no el bullet fijo que el
prompt tenía antes. Si `documents` está vacía, el nodo `RAG — Generate Answer` cae al
fallback silencioso del router y contesta genérico — es la señal de que la ingesta no corrió.

## Estado verificado el 2026-08-19

Probado de punta a punta contra el webhook de produccion. El chatbot **responde con
contenido real recuperado de Supabase**:

> *"que examenes internacionales puedo rendir?"* ->
> "Puede rendir los siguientes examenes internacionales: ECECE (a partir de nivel A2),
> TOEIC Bridge (A2), TOEIC (B1) y TOEFL iBT (B2)."

Ingesta: 9 documentos (5 FAQ + 4 cursos). `avisos` esta vacio en la base, por eso no aporta.

### El indice vectorial (ya resuelto)

Antes de borrarlo, la busqueda devolvia **1 solo documento** sin importar el `match_count`. El culpable es el
indice `ivfflat` con `lists = 100` sobre una tabla de 9 filas: reparte los vectores en listas
casi vacias y, como `ivfflat.probes` vale 1 por default, escanea una sola lista. Sintoma
tipico: preguntas sobre cursos contestan "no tengo esa informacion" aunque los documentos
esten cargados.

Se resolvio corriendo en Supabase -> SQL Editor:

```sql
drop index if exists documents_embedding_idx;
```

Despues del drop, `match_documents` con `match_count: 4` devuelve 4 filas y las respuestas
combinan FAQ + cursos correctamente.

Con menos de ~1000 filas el scan secuencial es exacto e instantaneo. Recrear el indice
recien cuando la tabla crezca, con `lists` proporcional (filas/1000) y subiendo `probes`.

### Correcciones aplicadas a los workflows

| Que estaba mal | Correccion |
|---|---|
| `$helpers.httpRequest` no existe en n8n 2.x (ni `fetch` ni `$http` en el sandbox) | Se usa `this.helpers.httpRequest`, capturado como `const helpers = this.helpers`. Afectaba a `RAG - Generate Answer`, `Save Session API` y a la ingesta |
| `text-embedding-004` retirado por Google | `gemini-embedding-001` con `outputDimensionality: 768` (mantiene el esquema de la tabla) |
| `llama-3.3-70b-versatile` retirado por Groq | `openai/gpt-oss-120b` (soporta `response_format: json_object`, que el router necesita) |
| `Fuera Scope - Format Response` leia `$('Parse Intent')` y descartaba la respuesta del RAG | Lee `$input.first().json` |
| El `catch` del nodo RAG se tragaba los errores sin dejar rastro | Expone el motivo en `_rag_error` sin cambiar el fallback |
| Nodo `Webhook` en modo `responseNode` sin `onError` | `onError: continueRegularOutput` |

### Gotchas del entorno

- **Actualizar un workflow por `PUT /api/v1/workflows/{id}` desregistra el webhook** aunque
  `active` siga en `true`. Hay que desactivar y reactivar para que vuelva a responder.
- La instancia esta detras de Cloudflare: los requests sin `User-Agent` de browser reciben
  `403 error 1010`. Aplica igual a la API de Groq.
- La ingesta usa trigger manual, asi que la API publica no puede dispararla: hay que abrirla
  en el editor y darle *Execute workflow*.

### Pruebas finales (2026-08-19)

| Consulta | Resultado |
|---|---|
| "que examenes internacionales puedo rendir?" | Cita ECECE, TOEIC Bridge, TOEIC y TOEFL iBT desde el FAQ |
| "que modalidades ofrecen y cuanto sale la cuota?" | Combina modalidades (FAQ) con English A1 - Beginners $8.500 (cursos) |
| "tienen clases de aleman los sabados?" | No alucina: deriva a secretaria |
| Conversacion de 2 turnos | Mantiene el contexto ("de esas tres...") |
| Persistencia de sesion | 2 turnos por sesion en `chat_sessions` via `/chatbot/session` |

Nota sobre el contrato del backend: `GET /chatbot/session/{id}` responde
`{"ok": true, "session": {...}}` — la sesion va en la clave `session`, no en `data`.
