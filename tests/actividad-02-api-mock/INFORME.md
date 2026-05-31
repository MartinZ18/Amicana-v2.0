# Informe — Actividad 2: API Testing · Mocking · Pruebas Híbridas (Playwright)

**Proyecto:** AMICANA 2.0  
**Herramienta:** Playwright  
**Total de casos:** 29 (api: 13 · mocking: 10 · híbrida: 6)  
**Resultado:** 29 passed / 0 failed

---

## Tabla de diseño de pruebas

### api.spec.js — API Testing sobre endpoints reales

| ID | Describe | Objetivo | Entradas | Resultado esperado |
|----|----------|----------|----------|--------------------|
| TC-API-01 | Autenticación | POST /login con credenciales válidas devuelve token JWT | `POST /login` form-encoded con usuario creado en `beforeAll` | HTTP 200, `access_token` con 3 partes JWT, `token_type: bearer` |
| TC-API-02 | Autenticación | POST /login con credenciales inválidas devuelve error 4xx | `POST /login` con usuario y contraseña inexistentes | HTTP 400/401/403, body con `detail` o `mensaje` |
| TC-API-03 | Registro | POST /auth/register con datos válidos crea la cuenta | Email único, nombre, password `TestPass2024!`, rol `alumno` | HTTP 200, `ok: true` |
| TC-API-04 | Registro | POST /auth/register con email duplicado devuelve error | Email ya registrado en `beforeAll` | HTTP 400 o 409 |
| TC-API-05 | Crear + UI | Alumno creado por API puede autenticarse y panel muestra su sesión | API register → API login → UI login → `sessionStorage` | URL cambia a `alumno.html`; JWT en storage tiene `sub` igual al email |
| TC-API-06 | Crear + UI | Perfil del alumno creado por API es accesible via /auth/me | Register → login → `GET /auth/me` con Bearer token | HTTP 200, `nombre` y `rol: alumno` correctos |
| TC-API-07 | Modificación | PUT /perfil actualiza el teléfono del usuario | Bearer token del usuario de `beforeAll`, nuevo teléfono | HTTP 200, `ok: true` |
| TC-API-08 | Modificación | /perfil refleja los datos actualizados tras PUT | PUT teléfono → GET /perfil con mismo token | `perfil.telefono` igual al valor enviado |
| TC-API-09 | Eliminación | DELETE /alumnos/{id} elimina el alumno (admin) | Token admin + ID del alumno creado para el test | HTTP 200 o 204 |
| TC-API-10 | Eliminación | Alumno eliminado no puede iniciar sesión | DELETE alumno → POST /login con sus credenciales | HTTP 400/401/403/404 |
| TC-API-11 | Infraestructura | GET /Prueba devuelve estado healthy | Sin autenticación | HTTP 200, body con campo `mensaje` |
| TC-API-12 | Infraestructura | GET /mis-cuotas sin token devuelve 401 | Sin header `Authorization` | HTTP 401 o 403 |
| TC-API-13 | Infraestructura | GET /mis-cuotas con token válido devuelve 200 | Bearer token del usuario de `beforeAll` | HTTP 200, `ok: true`, campo `cuotas` es array |

### mocking.spec.js — Intercepción de red con page.route()

| ID | Patrón | Objetivo | Mock aplicado | Resultado esperado |
|----|--------|----------|---------------|--------------------|
| TC-MOCK-01 | Error 500 | Error 500 en /login muestra mensaje de error en UI | `POST /login` → HTTP 500 | `[data-testid="login-message"]` visible; URL permanece en `index.html` |
| TC-MOCK-02 | Error 500 | Error 500 en /mis-cuotas no muestra cuotas reales | Login exitoso + `POST /mis-cuotas` → HTTP 500 | Lista de cuotas no contiene meses reales |
| TC-MOCK-03 | Error 500 | Respuesta exitosa falsa de login redirige al panel de alumno | `mockLoginExitoso()` + `blockUnmatchedApi()` | URL cambia a `alumno.html` |
| TC-MOCK-04 | Lista mockeada | Lista de cuotas mockeada renderiza ítems en UI | `GET /mis-cuotas` → 3 cuotas con Enero/Febrero/Marzo | `[data-testid="lista-cuotas"]` contiene "Enero" y "Febrero" |
| TC-MOCK-05 | Lista mockeada | Stats del panel reflejan totales de la lista mockeada | Mock con `pendientes: 2`, `pagadas: 1` | `stat-pendientes` = 2, `stat-pagadas` = 1 |
| TC-MOCK-06 | Lista mockeada | Link de pago MP es interceptable via mock | `POST /pagar-cuota/**` → `init_point` conocido | `fetch('/pagar-cuota/1')` devuelve el `init_point` mockeado |
| TC-MOCK-07 | Estado vacío | Lista vacía muestra mensaje de estado vacío | `GET /mis-cuotas` → `cuotas: []` | `[data-testid="lista-cuotas"]` contiene "No tenés cuotas asignadas" |
| TC-MOCK-08 | Estado vacío | Stats muestran cero cuando no hay cuotas | `GET /mis-cuotas` → todos los contadores en 0 | `stat-pendientes` contiene "0" |
| TC-MOCK-09 | Error 401 | 401 en /mis-cuotas fuerza logout y redirige al login | `GET /mis-cuotas` → HTTP 401 desde `alumno.html` | URL regresa a `index.html` |
| TC-MOCK-10 | Error 401 | Token mockeado queda en sessionStorage con formato JWT correcto | Token de valor conocido via `mockLoginExitoso()` | `sessionStorage.getItem('token')` = token exacto, 3 partes |

### hibrida.spec.js — Patrón API Setup + UI Verify

| ID | Flujo | Objetivo | Pasos | Resultado esperado |
|----|-------|----------|-------|--------------------|
| TC-HYB-01 | API Setup → UI Verify | Usuario creado por API puede iniciar sesión en la UI | Register API → login UI | URL cambia a `alumno.html`; token en `sessionStorage` |
| TC-HYB-02 | API Setup → UI error | Usuario real falla en UI con contraseña incorrecta | Register API → login UI con clave errónea | `login-message` visible; URL no cambia a `alumno.html` |
| TC-HYB-03 | API Setup → JWT verify | Email del alumno está en el JWT almacenado en UI | Register API → login UI → decode JWT | `payload.sub` igual al email registrado |
| TC-HYB-04 | Health + API + UI | Backend sano permite ciclo completo alta + login | GET /Prueba 200 → register → login UI | URL cambia a `alumno.html` |
| TC-HYB-05 | Modificar → API verify | Modificar teléfono via API se refleja en /auth/me | Register → PUT /perfil → GET /perfil → login UI | `perfil.telefono` actualizado; sesión UI sigue activa |
| TC-HYB-06 | Eliminar → UI verify | Alumno eliminado via API no puede iniciar sesión en UI | Register → login para ID → delete admin → login UI | `login-message` visible; URL no cambia a `alumno.html` |

---

## Por qué API real, mocking o híbrida

### API real (`api.spec.js`)

Se usa la API real cuando el objetivo es **validar el contrato del servidor**: que los endpoints existen, que los códigos de estado son correctos y que la forma de la respuesta es la esperada. No puede reemplazarse con mocks porque el propósito es verificar el comportamiento del backend real, incluyendo validaciones Pydantic, acceso a la base de datos y manejo de errores.

Cubre el ciclo CRUD completo: autenticación, registro, visualización de perfil, modificación y eliminación. También verifica que el modelo de seguridad (rutas protegidas, 401 sin token) funcione correctamente.

### Mocking (`mocking.spec.js`)

Se usa `page.route()` cuando se quiere **aislar la UI del backend** para:
- Simular errores difíciles de reproducir (500, 401 en producción).
- Probar estados extremos: respuestas vacías, datos controlados, expiración de sesión.
- Ejecutar tests sin depender de la base de datos ni de un backend corriendo.
- Garantizar velocidad y reproducibilidad total.

Los cuatro patrones cubiertos son: error 500 y su efecto en UI, lista de resultados con datos controlados, estados vacíos y errores de autorización.

### Híbrida (`hibrida.spec.js`)

Combina llamadas reales a la API para **preparar el estado** (crear usuarios con datos controlados) con verificación visual desde la UI. Esto garantiza que:
- El flujo completo de extremo a extremo funcione.
- La UI muestre correctamente los datos persistidos en la base de datos real.
- Las operaciones de modificación y eliminación tengan efecto observable desde la interfaz.

---

## Incidentes encontrados durante la implementación

Ver [`INCIDENTES.md`](INCIDENTES.md) para el detalle completo.

| ID | Test afectado | Error | Causa raíz resumida |
|----|--------------|-------|---------------------|
| INC-01 | TC-API-01 | HTTP 400 en lugar de 200 | Password del admin proviene de `ADMIN_SEED_PASSWORD` env var |
| INC-02 | TC-API-03 | `Expected "ok" / Received {"mensaje": ...}` | Endpoint `/usuarios` (alias deprecated) no usa convención `ok: bool` |
| INC-03 | TC-API-07 | HTTP 400 en `obtenerToken()` | Misma causa que INC-01 |
| INC-04 | TC-MOCK-03 | URL no cambia a `alumno.html` | `alumno.html` llama `/perfil`, `/avisos` en `onload`; JWT falso → 401 real → `logout()` |
| INC-05 | TC-MOCK-07 | `element(s) not found` | Misma causa que INC-04 + texto esperado incorrecto |
| INC-06 | TC-MOCK-10 | `Execution context was destroyed` | Misma causa que INC-04 |
| INC-07 | TC-HYB-04 | URL no cambia a panel esperado | Misma causa que INC-01 |

**Solución INC-01/03/07:** Los tests crean su propio usuario en `beforeAll` con credenciales controladas.  
**Solución INC-04/05/06:** `blockUnmatchedApi()` absobe llamadas no mockeadas devolviendo `200 {}` (catch-all LIFO).

---

## Evidencia de ejecución

```bash
# Correr la actividad completa
npx playwright test --project=actividad-02-api-mock

# Ver reporte HTML con screenshots y videos
npx playwright show-report
```

El reporte HTML en `playwright-report/` incluye estado de cada test, screenshots por paso, video completo y trace viewer para debugging.
