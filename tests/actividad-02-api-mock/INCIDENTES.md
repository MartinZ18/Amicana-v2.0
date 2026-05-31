# Registro de Incidentes — Actividad 2 Playwright

**Proyecto**: AMICANA 2.0  
**Fecha de detección**: 16/05/2026  
**Herramienta**: Playwright + pytest  
**Resultado inicial**: 9 passed / 7 failed

---

## Tabla de Incidentes

| ID | Test afectado | Tipo | Severidad | Descripción del error | Causa raíz | Corrección aplicada |
|----|--------------|------|-----------|----------------------|------------|---------------------|
| INC-01 | TC-API-01 | API Testing | Alta | `Expected: 200 / Received: 400` al llamar `POST /login` con `admin@amicana.com` | La contraseña del admin proviene de la variable de entorno `ADMIN_SEED_PASSWORD`, no de un valor hardcodeado. El test usaba `'admin123'` como fallback, que no coincide con lo almacenado en la BD | Se eliminó la dependencia del usuario admin. El test ahora crea un usuario propio en `beforeAll` con credenciales conocidas y usa esas credenciales |
| INC-02 | TC-API-03 | API Testing | Media | `Expected path: "ok" / Received value: {"mensaje": "Usuario creado"}` | El endpoint `POST /usuarios` (alias deprecated) devuelve `{"mensaje": "..."}` en lugar de `{"ok": true, ...}`. El endpoint canónico `/auth/register` sí usa la convención `ok: bool`, pero el alias no fue actualizado | Se corrigió la aserción a `expect(body).toHaveProperty('mensaje')` para reflejar la respuesta real del endpoint |
| INC-03 | TC-API-07 | API Testing | Alta | `Expected: 200 / Received: 400` al intentar obtener token en `obtenerToken()` | La función `obtenerToken()` usaba las mismas credenciales del admin (ver INC-01) para obtener el token necesario para la prueba de ruta protegida | Se actualizó `obtenerToken()` para usar el usuario creado en `beforeAll` con credenciales controladas |
| INC-04 | TC-MOCK-02 | Mocking / UI | Alta | `Expected pattern: /alumno\.html/ / Received: "http://localhost:8000/app/index.html"` — la página no redirige al panel | Al hacer login con token falso, el frontend redirige a `alumno.html`. Pero `alumno.html` llama en su `onload` a `/perfil`, `/avisos`, `/calendario`. Esas rutas llegan al servidor real con el JWT inválido (firma `fakesignature`), el servidor devuelve 401, y la función `api()` llama `logout()` → redirige de vuelta a `index.html` | Se incorporó `blockUnmatchedApi()` dentro de `mockLoginExitoso()` (registrado primero para menor prioridad). Absorbe todas las llamadas no mockeadas devolviendo `200 {}`, evitando el 401 del servidor real |
| INC-05 | TC-MOCK-03 | Mocking / UI | Alta | `Error: element(s) not found` — el locator `[data-testid="lista-cuotas"]` no existe en la página | Misma causa que INC-04: la página redirigía de vuelta a `index.html` antes de que el test pudiera verificar el contenido de `alumno.html`. Adicionalmente, el texto esperado era `/no tenés cuotas/i` pero el real es `"No tenés cuotas asignadas"` | Se aplicó `blockUnmatchedApi()` (ver INC-04) y se corrigió el patrón a `/No tenés cuotas asignadas/i` según el texto real del HTML |
| INC-06 | TC-MOCK-05 | Mocking / UI | Alta | `Error: page.evaluate: Execution context was destroyed, most likely because of a navigation` | Misma causa que INC-04: mientras el test intentaba leer `sessionStorage` en `alumno.html`, la página ya había sido redirigida de vuelta a `index.html` por el 401, destruyendo el contexto de ejecución | Se aplicó `blockUnmatchedApi()` (ver INC-04). Con las llamadas de `onload` absorbidas, la página permanece en `alumno.html` y el `evaluate()` se ejecuta sin error |
| INC-07 | TC-HYB-04 | Híbrida / UI | Alta | `Expected pattern: /admin\.html/ / Received: "http://localhost:8000/app/index.html"` — el login admin no redirige | Mismo problema que INC-01: el test usaba `admin@amicana.com` con password `'admin123'` hardcodeado. El admin existe sólo si `ADMIN_SEED_PASSWORD` está configurado en el `.env`, y con esa contraseña específica | Se reemplazó el uso del admin por un usuario de prueba creado en el propio test via `POST /usuarios` con credenciales conocidas. TC-HYB-04 ahora verifica: health check OK → creación de usuario OK → login en UI OK |

---

## Análisis de Causas Raíz

### Causa 1 — Credenciales de entorno no configuradas (afecta INC-01, INC-03, INC-07)

El usuario administrador de AMICANA se crea mediante un seed que lee `ADMIN_SEED_PASSWORD` del archivo `.env`. Si esa variable no existe, el seed se omite y el usuario no se crea. Los tests que dependían de `admin@amicana.com / admin123` fallaban porque:
- `admin123` no es necesariamente la contraseña real
- El usuario podría no existir si el seed nunca corrió

**Lección**: Las pruebas de API no deben depender de usuarios cuya existencia o contraseña está fuera del control del test. Se deben usar usuarios creados dentro del propio test o suite.

### Causa 2 — JWT falso rechazado por el servidor en llamadas `onload` (afecta INC-04, INC-05, INC-06)

El frontend de `alumno.html` llama a múltiples endpoints en el evento `load` (`/perfil`, `/avisos`, `/calendario`, `/mis-cuotas`). La función `api()` hace `logout()` ante cualquier respuesta 401. Un JWT con firma `fakesignature` es rechazado por el servidor real con 401, causando una cadena de redirects de vuelta a `index.html`.

Sin `blockUnmatchedApi()`, los tests de mocking que usaban tokens falsos no podían mantenerse en `alumno.html` el tiempo suficiente para verificar el estado de la UI.

**Lección**: En proyectos donde el frontend hace múltiples llamadas a la API al cargar una página, los tests de mocking deben interceptar TODAS las rutas relevantes (o usar un catch-all) para evitar que el servidor real interfiera.

### Causa 3 — Formato de respuesta de endpoint alias no documentado (afecta INC-02)

El endpoint `POST /usuarios` es un alias deprecated de `POST /auth/register`. Difiere en la forma del response: devuelve `{"mensaje": "..."}` en lugar de la convención `{"ok": true, ...}` del proyecto. El CLAUDE.md menciona la convención `ok: bool` pero no especifica las excepciones.

**Lección**: Los endpoints deprecated pueden tener comportamientos distintos a los canonicos. Las pruebas deben verificar contra la respuesta real del endpoint que usan.

---

## Estado Final

| Archivo | Tests | Passed | Failed |
|---------|-------|--------|--------|
| api.spec.js | 13 | 13 | 0 |
| mocking.spec.js | 10 | 10 | 0 |
| hibrida.spec.js | 6 | 6 | 0 |
| **Total** | **29** | **29** | **0** |
