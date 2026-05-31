# Tests — AMICANA 2.0

Suite de pruebas automatizadas con **Playwright**. Cubre tres dimensiones: testing de UI, testing de API con mocking e híbrido, y regresión completa del sistema.

---

## Requisitos

| Herramienta | Versión | Necesaria para |
|-------------|---------|---------------|
| Node.js | 18+ | Playwright |
| Backend (`uvicorn`) | corriendo en `localhost:8000` | Todas las actividades |
| MySQL | corriendo | Actividad 2 (api.spec + hibrida.spec), Actividad 3 (tests API real) |

---

## Instalación

```bash
# Desde la raíz del proyecto (una sola vez)
npm install
npx playwright install chromium
```

---

## Ejecutar los tests

### Actividad 1 — UI Funcional

Pruebas de interfaz con mocking total de la API. **No requiere base de datos activa.**

```bash
npx playwright test --project=actividad-01-ui
```

### Actividad 2 — API + Mocking + Híbrido

```bash
# Todas las suites de la actividad 2
npx playwright test --project=actividad-02-api-mock

# Solo API testing (requiere BD)
npx playwright test --project=actividad-02-api-mock api.spec.js

# Solo mocking (no requiere BD)
npx playwright test --project=actividad-02-api-mock mocking.spec.js

# Solo híbridos (requiere BD)
npx playwright test --project=actividad-02-api-mock hibrida.spec.js
```

### Actividad 3 — Regresión

```bash
# Suite completa de regresión
npx playwright test --project=actividad-03-regresion

# Solo tests smoke (no requieren BD activa)
npx playwright test --project=actividad-03-regresion --grep @smoke
```

### Todos los tests

```bash
npx playwright test
```

### Ver reporte HTML (con screenshots y videos)

```bash
npx playwright show-report
```

---

## Estructura de archivos

```
tests/
├── actividad-01-ui/
│   ├── login.spec.js              ← 6 tests de UI — autenticación mockeada
│   └── INFORME.md                 ← Tabla de casos, incidentes
│
├── actividad-02-api-mock/
│   ├── api.spec.js                ← 13 tests — API real (auth, CRUD, rutas protegidas)
│   ├── mocking.spec.js            ← 10 tests — intercepción con page.route() (4 patrones)
│   ├── hibrida.spec.js            ← 6 tests  — API Setup + UI Verify
│   ├── INFORME.md                 ← Tabla de diseño, justificación, evidencia
│   └── INCIDENTES.md              ← 7 incidentes detectados y resueltos
│
├── actividad-03-regresion/
│   ├── regresion.spec.js          ← 28 tests — suite de regresión (8 funcionalidades)
│   └── INFORME.md                 ← Tabla de diseño, arquitectura, cobertura
│
└── README.md                      ← Este archivo
```

---

## Resumen de cobertura

### Actividad 1

| Archivo | Tests | BD necesaria |
|---------|-------|:---:|
| `login.spec.js` | 6 | No |

### Actividad 2

| Archivo | Tests | BD necesaria | Descripción |
|---------|-------|:---:|-------------|
| `api.spec.js` | 13 | Sí | Auth, registro, perfil, eliminación, rutas protegidas |
| `mocking.spec.js` | 10 | No | Errores 500/401, lista mockeada, estados vacíos, token en storage |
| `hibrida.spec.js` | 6 | Sí | Crear/modificar/eliminar por API → validar en UI |
| **Total** | **29** | | |

### Actividad 3

| Archivo | Tests | BD necesaria | Descripción |
|---------|-------|:---:|-------------|
| `regresion.spec.js` | 28 | Parcial | 8 FC: login, alta, MP, modificación, logout, validaciones, mensajes, eliminación |
| **Total** | **28** | | |

---

## Notas importantes

### Actividad 1 — mocking total

Todos los tests usan `page.route()` para interceptar las llamadas a la API. El backend solo necesita estar corriendo para servir los archivos HTML estáticos.

### Actividad 2 y 3 — `blockUnmatchedApi`

`alumno.html` realiza múltiples llamadas a la API en el evento `load` (`/perfil`, `/avisos`, `/calendario`, `/mis-cuotas`). La función `api()` del frontend ejecuta `logout()` ante cualquier respuesta `401`. Los tests de mocking incorporan `blockUnmatchedApi()` como catch-all que absorbe todas las rutas no mockeadas devolviendo `200 {}`, evitando que el servidor real devuelva `401` con tokens falsos y rompa el flujo del test.

### Actividad 2 — usuario de prueba en `beforeAll`

Los tests de API no dependen del usuario administrador (cuya contraseña proviene de `ADMIN_SEED_PASSWORD`). En su lugar, `api.spec.js` crea un usuario de prueba en `test.beforeAll()` con credenciales conocidas y controladas.

### Actividad 3 — tests admin con `test.skip()`

Los tests de FC-08 que requieren rol admin intentan credenciales predefinidas. Si ninguna funciona, llaman `test.skip()` y se omiten sin fallo.

### Variables de entorno para tests

Los tests de API y híbridos usan el backend real. No se necesitan variables de entorno adicionales para Playwright. Los usuarios de prueba se crean dinámicamente dentro de cada suite.

---

## Configuración de Playwright

Ver `playwright.config.js` en la raíz. Configuración principal:

| Parámetro | Valor |
|-----------|-------|
| `baseURL` | `http://localhost:8000` |
| `workers` | 1 (secuencial) |
| `reporter` | `list` + `html` |
| `screenshot` | `on` (siempre) |
| `video` | `on` (siempre) |
| `trace` | `retain-on-failure` |
