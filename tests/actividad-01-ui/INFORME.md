# Informe — Actividad 1: Testing UI Funcional (Playwright)

## Objetivo del caso automatizado

Verificar el comportamiento visual e interactivo de las principales funcionalidades del sistema AMICANA 2.0 desde la perspectiva del usuario final, sin depender del estado de la base de datos.
Los tests cubren tres flujos críticos: autenticación, gestión de alumnos y visualización de cuotas.

---

## Precondiciones

| Condición | Detalle |
|-----------|---------|
| Backend | FastAPI corriendo en `http://localhost:8000` (solo para servir los archivos estáticos) |
| Base de datos | **No requerida** — todas las respuestas API están mockeadas con `page.route()` |
| Navegador | Chromium (instalado con `npx playwright install chromium`) |
| Node.js | ≥ 18 |
| Dependencias | `npm install @playwright/test` |

---

## Pasos cubiertos por archivo spec

### `01-login.spec.js` — Autenticación

| ID | Escenario | Pasos | Resultado esperado |
|----|-----------|-------|--------------------|
| CP-L01 | Login válido admin | 1. Ir a `/app/index.html` 2. Ingresar credenciales admin 3. Hacer clic en "Ingresar" | Redirección a `admin.html` |
| CP-L02 | Contraseña incorrecta | 1. Ingresar email válido y contraseña errónea 2. Hacer clic en "Ingresar" | Mensaje de error visible con texto "incorrecta" |
| CP-L03 | Campos vacíos | 1. Hacer clic en "Ingresar" sin completar campos | El formulario no se envía; `validity.valueMissing = true` en el campo email |
| CP-L04 | Usuario inexistente | 1. Ingresar email inexistente 2. Hacer clic en "Ingresar" | Mensaje de error visible con texto "no encontrado" |



---

## Datos de prueba

| Variable | Valor |
|----------|-------|
| Admin email | `admin@amicana.com` |
| Admin rol JWT | `admin` |
| Alumno email | `alumno@test.com` |
| Alumno rol JWT | `alumno` |
| Cuota mock ID | 1, 2, 3 |
| Cuota mock concepto | `Cuota Marzo 2026`, `Cuota Abril 2026`, `Cuota Febrero 2026` |
| Cuota mock estados | `pendiente`, `vencida`, `pagada` |
| DNI inválido para test | `ABCD1234` (contiene letras) |

---

## Resultado esperado

Todos los tests de Actividad 1 deben pasar (**PASS**) sin necesitar base de datos activa,
ya que la capa de API está completamente mockeada con `page.route()`.

---

## Incidentes encontrados

### INC-01 — DNI sin validación client-side (resuelto)

- **Detectado en:** CP-A03
- **Descripción:** El campo DNI del formulario de alta de alumno no tenía validación de formato en el frontend. Era posible ingresar letras o valores arbitrarios.
- **Impacto:** Un evaluador podría ingresar un DNI inválido que el backend almacena sin error.
- **Resolución:** Se agregó validación en `guardarAlumno()` en `admin.html`: el DNI debe tener entre 7 y 8 dígitos numéricos (`/^\d{7,8}$/`).
- **Estado:** ✅ Resuelto en esta iteración.

### INC-02 — CP-C05 dependía del comportamiento del popup blocker

- **Detectado en:** CP-C05
- **Descripción:** El click en "Pagar con MercadoPago" usaba `window.open()` con el link de pago. Los navegadores headless pueden bloquear popups, haciendo el test no determinístico.
- **Resolución:** Se reemplazó `window.open()` por mostrar un elemento `<a data-testid="mp-link">` directamente en la UI después de cerrar el modal. El test ahora verifica la presencia del link en el DOM con `expect(page.locator('[data-testid="mp-link"]')).toBeVisible()` y su atributo `href`.
- **Estado:** ✅ Resuelto — test determinístico sin dependencia de popup blocker.

### INC-03 — pagarConMP() usaba alert() ante errores

- **Detectado en:** CP-C05 / CP-MOCK02
- **Descripción:** La función `pagarConMP()` en `alumno.html` usaba `alert()` nativo para mostrar errores, lo que requería manejar el dialog del navegador en los tests en lugar de verificar un elemento del DOM.
- **Resolución:** Se reemplazó `alert()` por `showMsg('modalPagarMsg', ...)`. Se agregó un div `<div id="modalPagarMsg" data-testid="modal-pagar-msg">` en el modal de pago. Se agregó la función helper `showMsg()` en `alumno.html`. El test CP-MOCK02 ahora usa `expect(page.locator('[data-testid="modal-pagar-msg"]')).toContainText(...)`.
- **Estado:** ✅ Resuelto — errores verificables desde el DOM.
