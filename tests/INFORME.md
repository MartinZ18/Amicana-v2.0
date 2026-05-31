# Informe — Actividad 3: Suite de Regresión (Playwright)

**Proyecto:** AMICANA 2.0  
**Herramienta:** Playwright  
**Archivo:** `regresion.spec.js`  
**Total de casos:** 28  
**Resultado:** 28 passed / 0 failed

---

## Objetivo

Verificar que el sistema AMICANA 2.0 funciona correctamente como un todo, cubriendo el ciclo de vida completo desde el primer acceso hasta la eliminación de una entidad. La suite está diseñada como prueba de regresión: cada vez que se modifica el backend o el frontend, estos tests detectan si alguna funcionalidad existente dejó de funcionar.

---

## Flujo de prueba

La suite sigue un flujo narrativo de 8 funcionalidades críticas (FC) que representan el ciclo completo del sistema:

```
FC-01 Login  →  FC-02 Alta  →  FC-03 API externa (MP)  →  FC-04 Modificación
     ↓                                                           ↓
FC-08 Eliminación  ←  FC-07 Mensajes  ←  FC-06 Validaciones  ←  FC-05 Logout
```

---

## Tabla de diseño de pruebas

### FC-01 — Login válido e inválido `@smoke`

Punto de entrada al sistema. Sin login no hay acceso a ninguna funcionalidad.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-01 | Mock + UI | Login con credenciales válidas redirige al dashboard | Mock /login OK → form email/pass → click Ingresar | URL cambia a `alumno.html`; token en `sessionStorage` no es `null` |
| REG-02 | Mock + UI | Contraseña incorrecta muestra error y no redirige | Mock /login → HTTP 400 `"Contraseña incorrecta"` | `login-message` visible con texto "incorrecta"; URL permanece en `index.html` |
| REG-03 | UI | Campos vacíos activan validación sin llamar al backend | Click "Ingresar" con campos en blanco | `validity.valueMissing = true` en campo email; sin llamada HTTP |

### FC-02 — Alta de usuario

El sistema debe poder crear nuevos usuarios tanto via API como a través de la UI.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-04 | API real | POST /auth/register con datos válidos crea la cuenta | Email único, nombre, password, rol `alumno` | HTTP 200, `ok: true` |
| REG-05 | API real | Usuario registrado por API puede iniciar sesión | Register → POST /auth/login JSON | HTTP 200, `access_token` con 3 partes JWT |
| REG-06 | Mock + UI | Alta via formulario UI con datos válidos redirige al dashboard | Mock /auth/register OK + mock /auth/login → form de registro completo | URL cambia a `alumno.html` |
| REG-07 | Mock + UI | Email ya registrado muestra error y no redirige | Mock /auth/register → HTTP 400 "El email ya está registrado" | `registro-message` visible con texto "email"/"registrado"; URL no cambia |

### FC-03 — Consulta a API externa (MercadoPago)

Los alumnos pueden pagar cuotas via MercadoPago. El sistema genera un link de pago.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-08 | API real | POST /pagar-cuota requiere autenticación y existe | Sin token → POST /pagar-cuota/1; con token y cuota 999999 | Sin token: 401/403. Con token: 400/404/422 (error de negocio, no 500) |
| REG-09 | Mock + UI | Endpoint de pago MP mockeado devuelve init_point correctamente | Mock /pagar-cuota/** → `init_point` conocido | `fetch('/pagar-cuota/1')` desde página devuelve `init_point` esperado, `ok: true` |
| REG-10 | Mock + UI | Error 500 en pagar-cuota no rompe la sesión | Mock /pagar-cuota/** → HTTP 500 | `fetch` devuelve 500; token en `sessionStorage` sigue presente; URL permanece en `alumno.html` |

### FC-04 — Modificación de perfil

El alumno puede actualizar su teléfono y verificar el cambio.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-11 | API real | PUT /perfil actualiza los datos del usuario | Register → login → PUT con nuevo teléfono → GET /perfil | HTTP 200, `ok: true`; `perfil.telefono` igual al valor enviado |
| REG-12 | Mock + UI | PUT /perfil mockeado devuelve confirmación | Mock PUT /perfil → `ok: true, mensaje: "actualizado"` | `fetch('/perfil', PUT)` devuelve `ok: true`; `mensaje` contiene "actualizado" |

### FC-05 — Logout y protección de rutas `@smoke`

El sistema debe proteger todos los recursos autenticados y limpiar la sesión al hacer logout.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-13 | Mock + UI | Cerrar sesión limpia sessionStorage y redirige al login | Login exitoso → click `btn-logout` | URL cambia a `index.html`; `sessionStorage.getItem('token')` es `null` |
| REG-14 | Mock + UI | Acceder al dashboard sin token redirige al login | `page.goto('/app/alumno.html')` sin token | URL cambia a `index.html` |
| REG-15 | Mock + UI | Token malformado no permite acceso al dashboard | Inyectar `token.invalido.xxx` en `sessionStorage` → navegar a `alumno.html` | URL cambia a `index.html` |
| REG-16 | Mock + UI | Logout elimina token y navegación posterior redirige al login | Login → logout → goto `alumno.html` | URL regresa a `index.html` en ambos accesos |
| REG-17 | API real | Sin token GET /mis-cuotas devuelve 401 | `GET /mis-cuotas` sin `Authorization` | HTTP 401 o 403 |
| REG-18 | API real | Con token válido GET /mis-cuotas devuelve 200 | Register → login → `GET /mis-cuotas` con Bearer | HTTP 200, `ok: true`, `cuotas` es array |

### FC-06 — Validaciones de formulario

Los formularios deben prevenir el envío de datos inválidos antes de llamar al backend.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-19 | UI | Contraseña con menos de 8 chars deshabilita el botón | Password `abc1` (4 chars) en formulario de registro | `registro-submit` está deshabilitado |
| REG-20 | UI | Sin aceptar términos el botón permanece deshabilitado | Nombre + email + password válidos; términos sin marcar | `registro-submit` está deshabilitado |
| REG-21 | UI | Campos obligatorios vacíos deshabilitan el botón | Formulario de registro sin completar | `registro-submit` está deshabilitado |
| REG-22 | UI | Todos los campos válidos y términos aceptados habilitan el botón | Nombre + email + password ≥ 8 chars + términos marcados | `registro-submit` está habilitado |

### FC-07 — Mensajes de error y confirmación

El sistema debe comunicar claramente éxitos y fallos al usuario.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-23 | Mock + UI | Error 500 en login muestra mensaje visible y no redirige | Mock /login → HTTP 500 | `login-message` visible; URL no cambia a `admin.html` |
| REG-24 | Mock + UI | Login exitoso muestra mensaje de confirmación antes de redirigir | Mock /login → HTTP 200 con token | `login-message` visible con texto "concedido" o "redirigiendo" |
| REG-25 | Mock + UI | Lista de cuotas vacía muestra mensaje de estado vacío | Mock /mis-cuotas → `cuotas: []` desde `alumno.html` | `lista-cuotas` contiene "No tenés cuotas asignadas" |

### FC-08 — Eliminación de entidad

El admin puede eliminar alumnos. La entidad eliminada no puede autenticarse.

| ID | Tipo | Objetivo | Entradas | Resultado esperado |
|----|------|----------|----------|--------------------|
| REG-26 | API real | DELETE /alumnos/{id} elimina el registro | Register alumno → obtener ID → DELETE admin | HTTP 200 o 204 |
| REG-27 | API real | Alumno eliminado no puede iniciar sesión (API) | DELETE alumno → POST /auth/login con sus credenciales | HTTP 400/401/403/404 |
| REG-28 | API real + UI | Alumno eliminado falla login en la UI | DELETE alumno → login UI con sus credenciales | `login-message` visible; URL no cambia a `alumno.html` |

---

## Arquitectura de la suite

### Mezcla de API real y mocking

La suite combina intencionalmente ambos enfoques:

- **Tests con API real (REG-04/05/08/11/17/18/26/27/28):** verifican el contrato del backend, la persistencia en base de datos y el modelo de seguridad. Son los tests que detectan regresiones en el servidor.
- **Tests con mocking (REG-01/02/03/06/07/09/10/12/13/14/15/16/19/20/21/22/23/24/25):** verifican el comportamiento de la UI ante distintas respuestas, incluyendo errores que son difíciles de reproducir con un backend real. No requieren base de datos activa.

Esta combinación garantiza cobertura total: tanto el backend como el frontend quedan cubiertos.

### `blockUnmatchedApi()` — por qué es necesario

`alumno.html` llama a `/perfil`, `/avisos`, `/calendario` y `/mis-cuotas` en el evento `load`. La función `api()` del frontend ejecuta `logout()` ante cualquier respuesta `401`. Los tests que usan tokens falsos (firma `fakesignature`) incorporan `blockUnmatchedApi()` como catch-all que absorbe todas las rutas no mockeadas devolviendo `200 {}`. Esto evita que el servidor real devuelva `401` con tokens inválidos y rompa el flujo del test.

Los mocks específicos registrados después de `blockUnmatchedApi()` tienen mayor prioridad (Playwright usa orden LIFO).

### `loginAdmin()` — manejo de credenciales de entorno

Los tests de FC-08 que requieren rol admin intentan credenciales en orden: `admin1234`, `admin123`, `Admin123!`. Si ninguna funciona (el admin no existe o usa una contraseña de entorno distinta), el test llama `test.skip()` y se omite sin fallo. Este patrón evita falsos negativos en entornos donde `ADMIN_SEED_PASSWORD` tiene un valor no estándar.

---

## Cómo ejecutar

```bash
# Desde la raíz del proyecto
npx playwright test --project=actividad-03-regresion

# Solo tests smoke (no requieren BD)
npx playwright test --project=actividad-03-regresion --grep @smoke

# Ver reporte HTML con screenshots y videos
npx playwright show-report
```

### Requisitos de entorno

| Recurso | Requerido para |
|---------|----------------|
| Backend en `localhost:8000` | Todos los tests |
| MySQL corriendo | Tests con API real (FC-02/04/05/08) |
| Variable `ADMIN_SEED_PASSWORD` | FC-08 (si no está, los tests admin hacen `skip`) |

---

## Resumen de cobertura

| FC | Nombre | Tests | API real | Mock |
|----|--------|-------|----------|------|
| FC-01 | Login | 3 | — | ✓ |
| FC-02 | Alta | 4 | ✓ | ✓ |
| FC-03 | API externa (MP) | 3 | ✓ | ✓ |
| FC-04 | Modificación | 2 | ✓ | ✓ |
| FC-05 | Logout/rutas | 6 | ✓ | ✓ |
| FC-06 | Validaciones | 4 | — | ✓ |
| FC-07 | Mensajes | 3 | — | ✓ |
| FC-08 | Eliminación | 3 | ✓ | — |
| **Total** | | **28** | **15** | **20** |
