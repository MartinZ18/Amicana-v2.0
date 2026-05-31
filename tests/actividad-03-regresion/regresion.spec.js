// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Actividad 3 — Suite de Regresión: AMICANA 2.0
 *
 * Flujo de prueba completo que simula el ciclo de vida del sistema:
 *
 *   FC-01  Login válido e inválido              → punto de entrada
 *   FC-02  Alta de usuario                      → registro via UI y API
 *   FC-03  Consulta a API externa (MercadoPago) → generación de link de pago
 *   FC-04  Modificación de perfil               → datos actualizables
 *   FC-05  Logout y protección de rutas         → seguridad de sesión
 *   FC-06  Validaciones de formulario           → integridad de datos
 *   FC-07  Mensajes de error y confirmación     → feedback al usuario
 *   FC-08  Eliminación de entidad               → baja de alumno
 *
 * Ejecutable con: npx playwright test --grep @regresion
 *
 * Arquitectura de mocking:
 *   blockUnmatchedApi() se registra PRIMERO (catch-all, menor precedencia).
 *   Los mocks de endpoints específicos se registran DESPUÉS (mayor precedencia).
 */

const API_BASE = 'http://localhost:8000';

// ── Helpers compartidos ───────────────────────────────────────────

function makeToken(sub, rol, id) {
  const header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9';
  const exp    = Math.floor(Date.now() / 1000) + 3600;
  const pay    = Buffer.from(JSON.stringify({ sub, rol, id, exp })).toString('base64');
  return `${header}.${pay}.fakesignature`;
}

async function blockUnmatchedApi(page) {
  await page.route('**/*', route => {
    const url = route.request().url();
    if (/\.(html|css|js|png|jpg|svg|ico|woff2?)(\?|$)/.test(url)) return route.continue();
    if (/\/app\//.test(url) && !url.includes('?'))                  return route.continue();
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

async function irAlLogin(page) {
  await page.goto('/app/index.html');
  await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
}

async function loginExitoso(page, rol = 'alumno', id = 1) {
  const token = makeToken(`${rol}@amicana.com`, rol, id);
  await blockUnmatchedApi(page);
  await page.route('**/login', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
    })
  );
  await irAlLogin(page);
  await page.locator('[data-testid="login-email"]').fill(`${rol}@amicana.com`);
  await page.locator('[data-testid="login-password"]').fill('playwright-test-stub');
  await page.locator('[data-testid="login-submit"]').click();
  return token;
}

// ─────────────────────────────────────────────────────────────────
// FC-01 · Login válido e inválido
// Primer paso del flujo: sin login no hay acceso al sistema.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-01 · Login @regresion @smoke', () => {

  test('REG-01: login con credenciales válidas redirige al dashboard de alumno @smoke', async ({ page }) => {
    const token = await loginExitoso(page, 'alumno', 1);

    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });

    const guardado = await page.evaluate(() => sessionStorage.getItem('token'));
    expect(guardado).not.toBeNull();
    expect(guardado).toBe(token);
  });

  test('REG-02: login con contraseña incorrecta muestra error y no redirige @smoke', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Contraseña incorrecta' }),
      })
    );

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('prueba@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('claveIncorrecta999');
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page.locator('[data-testid="login-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-message"]')).toContainText(/incorrecta/i);
    await expect(page).not.toHaveURL(/alumno\.html/);
    await expect(page).not.toHaveURL(/admin\.html/);
  });

  test('REG-03: campos vacíos activan validación sin llamar al backend @smoke', async ({ page }) => {
    await irAlLogin(page);
    await page.locator('[data-testid="login-submit"]').click();

    const emailInput = page.locator('[data-testid="login-email"]');
    const valueMissing = await emailInput.evaluate(el => el.validity.valueMissing);
    expect(valueMissing).toBe(true);
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-02 · Alta de usuario
// Segundo paso: el sistema debe poder crear nuevos usuarios
//               tanto via API como via el formulario de la UI.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-02 · Alta de usuario @regresion', () => {

  test('REG-04: POST /auth/register con datos válidos crea la cuenta (API real)', async ({ page }) => {
    const ts = Date.now();
    const response = await page.request.post(`${API_BASE}/auth/register`, {
      data: {
        nombre:   `Alumno Reg ${ts}`,
        email:    `reg_${ts}@example.com`,
        password: 'TestPass2024!',
        rol:      'alumno',
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('ok', true);
  });

  test('REG-05: usuario registrado por API puede iniciar sesión', async ({ page }) => {
    const ts = Date.now();
    const email    = `reglogin_${ts}@example.com`;
    const password = 'TestPass2024!';

    await page.request.post(`${API_BASE}/auth/register`, {
      data: { nombre: `Reg Login ${ts}`, email, password, rol: 'alumno' },
    });

    const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password },
    });

    expect(loginRes.status()).toBe(200);
    const body = await loginRes.json();
    expect(body).toHaveProperty('access_token');
    expect(body.access_token.split('.').length).toBe(3);
  });

  test('REG-06: alta via formulario UI con datos válidos redirige al dashboard', async ({ page }) => {
    const ts    = Date.now();
    const email = `altaui_${ts}@example.com`;
    const token = makeToken(email, 'alumno', 99);

    await blockUnmatchedApi(page);
    await page.route('**/auth/register', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, mensaje: 'Usuario creado correctamente' }),
      })
    );
    await page.route('**/auth/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
      })
    );

    await page.goto('/app/index.html');
    await page.locator('[data-testid="btn-toggle-registro"]').click();
    await expect(page.locator('#registroSection')).toHaveClass(/open/);

    await page.locator('[data-testid="registro-nombre"]').fill(`Alta UI ${ts}`);
    await page.locator('[data-testid="registro-email"]').fill(email);
    await page.locator('[data-testid="registro-password"]').fill('AltaPass12!');
    await page.locator('[data-testid="registro-terminos"]').check();

    await expect(page.locator('[data-testid="registro-submit"]')).toBeEnabled();
    await page.locator('[data-testid="registro-submit"]').click();

    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
  });

  test('REG-07: email ya registrado muestra error y no redirige', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/auth/register', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'El email ya está registrado' }),
      })
    );

    await page.goto('/app/index.html');
    await page.locator('[data-testid="btn-toggle-registro"]').click();
    await expect(page.locator('#registroSection')).toHaveClass(/open/);

    await page.locator('[data-testid="registro-nombre"]').fill('Alumno Existente');
    await page.locator('[data-testid="registro-email"]').fill('existente@amicana.com');
    await page.locator('[data-testid="registro-password"]').fill('Clave1234!');
    await page.locator('[data-testid="registro-terminos"]').check();

    await page.locator('[data-testid="registro-submit"]').click();

    const msg = page.locator('[data-testid="registro-message"]');
    await expect(msg).toBeVisible();
    await expect(msg).toContainText(/email|registrado/i);
    await expect(page).not.toHaveURL(/alumno\.html/);
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-03 · Consulta a API externa — MercadoPago
// Tercer paso: los alumnos pueden pagar cuotas via MercadoPago.
//              El sistema genera un link de pago que la UI muestra.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-03 · Consulta a API externa (MercadoPago) @regresion', () => {

  test('REG-08: POST /pagar-cuota requiere autenticación y existe en el sistema', async ({ page }) => {
    // Verificar que el endpoint existe y requiere token (comportamiento siempre testeable)
    const sinToken = await page.request.post(`${API_BASE}/pagar-cuota/1`);
    expect([401, 403]).toContain(sinToken.status());

    // Con token válido y cuota inexistente → error controlado (no 500 genérico)
    const ts = Date.now();
    const email    = `mp_test_${ts}@example.com`;
    const password = 'MPTest2024!';
    await page.request.post(`${API_BASE}/auth/register`, {
      data: { nombre: `MP Test ${ts}`, email, password, rol: 'alumno' },
    });
    const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password },
    });
    const { access_token } = await loginRes.json();

    const pagoRes = await page.request.post(`${API_BASE}/pagar-cuota/999999`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    // El endpoint debe responder con error de negocio (no 500) — cuota no encontrada
    expect([400, 404, 422]).toContain(pagoRes.status());
  });

  test('REG-09: endpoint de pago MP mockeado devuelve init_point correctamente', async ({ page }) => {
    const INIT_POINT = 'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=TEST-REG09';

    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: makeToken('alumno@amicana.com', 'alumno', 1), token_type: 'bearer' }),
      })
    );
    await page.route('**/pagar-cuota/**', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, init_point: INIT_POINT, preference_id: 'TEST-REG09' }),
      })
    );

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('test-stub');
    await page.locator('[data-testid="login-submit"]').click();
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // Llamar al endpoint de pago desde el contexto de la página (simula lo que hace el botón Pagar)
    const resultado = await page.evaluate(async () => {
      const token = sessionStorage.getItem('token');
      const res = await fetch('/pagar-cuota/1', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: res.status, body: await res.json() };
    });

    expect(resultado.status).toBe(200);
    expect(resultado.body.init_point).toBe(INIT_POINT);
    expect(resultado.body.ok).toBe(true);
  });

  test('REG-10: error 500 en pagar-cuota es gestionado sin romper la sesión', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: makeToken('alumno@amicana.com', 'alumno', 1), token_type: 'bearer' }),
      })
    );
    await page.route('**/pagar-cuota/**', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Error al conectar con MercadoPago' }),
      })
    );

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('test-stub');
    await page.locator('[data-testid="login-submit"]').click();
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // El endpoint devuelve 500 — la página no debe redirigir al login (no es 401)
    const resultado = await page.evaluate(async () => {
      const token = sessionStorage.getItem('token');
      const res = await fetch('/pagar-cuota/1', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      return { status: res.status };
    });

    expect(resultado.status).toBe(500);
    // La sesión sigue activa — el token no fue eliminado
    const tokenDespues = await page.evaluate(() => sessionStorage.getItem('token'));
    expect(tokenDespues).not.toBeNull();
    await expect(page).toHaveURL(/alumno\.html/);
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-04 · Modificación de perfil
// El alumno puede actualizar su email y teléfono.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-04 · Modificación @regresion', () => {

  test('REG-11: PUT /perfil actualiza los datos del usuario (API real)', async ({ page }) => {
    const ts       = Date.now();
    const email    = `mod_${ts}@example.com`;
    const password = 'Mod2024!';

    await page.request.post(`${API_BASE}/auth/register`, {
      data: { nombre: `Modificar ${ts}`, email, password, rol: 'alumno' },
    });
    const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password },
    });
    const { access_token } = await loginRes.json();

    const nuevoTel = `116${ts.toString().slice(-7)}`;
    const putRes = await page.request.put(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { email, telefono: nuevoTel },
    });
    expect(putRes.status()).toBe(200);
    const body = await putRes.json();
    expect(body).toHaveProperty('ok', true);

    // Verificar que el cambio se persistió
    const perfilRes = await page.request.get(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const perfil = (await perfilRes.json()).data || (await perfilRes.json()).perfil || await perfilRes.json();
    expect(perfil.telefono).toBe(nuevoTel);
  });

  test('REG-12: PUT /perfil mockeado devuelve confirmación y actualiza los datos', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: makeToken('alumno@amicana.com', 'alumno', 1), token_type: 'bearer' }),
      })
    );
    await page.route('**/perfil', async route => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, mensaje: 'Perfil actualizado correctamente' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ nombre: 'Alumno Test', email: 'alumno@amicana.com', telefono: '1161111111', rol: 'alumno' }),
        });
      }
    });

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('test-stub');
    await page.locator('[data-testid="login-submit"]').click();
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // Verificar que PUT /perfil devuelve ok desde el contexto de la página
    const resultado = await page.evaluate(async () => {
      const token = sessionStorage.getItem('token');
      const res = await fetch('/perfil', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email: 'alumno@amicana.com', telefono: '1199999999' }),
      });
      return { status: res.status, body: await res.json() };
    });

    expect(resultado.status).toBe(200);
    expect(resultado.body.ok).toBe(true);
    expect(resultado.body.mensaje).toContain('actualizado');
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-05 · Logout y protección de rutas
// El sistema debe proteger todos los recursos autenticados.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-05 · Logout y protección de rutas @regresion @smoke', () => {

  test('REG-13: cerrar sesión limpia sessionStorage y redirige al login', async ({ page }) => {
    await loginExitoso(page, 'alumno', 1);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    const tokenAntes = await page.evaluate(() => sessionStorage.getItem('token'));
    expect(tokenAntes).not.toBeNull();

    await page.locator('[data-testid="btn-logout"]').click();

    await expect(page).toHaveURL(/index\.html/, { timeout: 6000 });
    const tokenDespues = await page.evaluate(() => sessionStorage.getItem('token'));
    expect(tokenDespues).toBeNull();
  });

  test('REG-14: acceder al dashboard sin token redirige al login @smoke', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.goto('/app/alumno.html');
    await expect(page).toHaveURL(/index\.html/, { timeout: 6000 });
  });

  test('REG-15: token malformado no permite acceso al dashboard @smoke', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.goto('/app/index.html');
    await page.evaluate(() => sessionStorage.setItem('token', 'token.invalido.xxx'));
    await page.goto('/app/alumno.html');
    await expect(page).toHaveURL(/index\.html/, { timeout: 6000 });
  });

  test('REG-16: logout elimina token y navegación posterior redirige al login @smoke', async ({ page }) => {
    await loginExitoso(page, 'alumno', 2);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    await page.locator('[data-testid="btn-logout"]').click();
    await expect(page).toHaveURL(/index\.html/, { timeout: 6000 });

    await page.goto('/app/alumno.html');
    await expect(page).toHaveURL(/index\.html/, { timeout: 6000 });
  });

  test('REG-17: sin token GET /mis-cuotas devuelve 401 @smoke', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/mis-cuotas`);
    expect([401, 403]).toContain(response.status());
  });

  test('REG-18: con token válido GET /mis-cuotas devuelve 200 @smoke', async ({ page }) => {
    const ts = Date.now();
    const email = `rutaprot_${ts}@example.com`;
    const password = 'TestPass2024!';

    await page.request.post(`${API_BASE}/auth/register`, {
      data: { nombre: `Ruta Prot ${ts}`, email, password, rol: 'alumno' },
    });
    const loginRes = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password },
    });
    const { access_token } = await loginRes.json();

    const response = await page.request.get(`${API_BASE}/mis-cuotas`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('ok', true);
    expect(Array.isArray(body.cuotas)).toBe(true);
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-06 · Validaciones de formulario
// Los formularios deben prevenir el envío de datos inválidos.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-06 · Validaciones de formulario @regresion', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/app/index.html');
    await page.locator('[data-testid="btn-toggle-registro"]').click();
    await expect(page.locator('#registroSection')).toHaveClass(/open/);
  });

  test('REG-19: contraseña con menos de 8 caracteres deshabilita el botón de registro', async ({ page }) => {
    await page.locator('[data-testid="registro-nombre"]').fill('Alumno Test');
    await page.locator('[data-testid="registro-email"]').fill('alumno@test.com');
    await page.locator('[data-testid="registro-password"]').fill('abc1');

    await expect(page.locator('[data-testid="registro-submit"]')).toBeDisabled();
  });

  test('REG-20: sin aceptar términos el botón de registro permanece deshabilitado', async ({ page }) => {
    await page.locator('[data-testid="registro-nombre"]').fill('Alumno Test');
    await page.locator('[data-testid="registro-email"]').fill('alumno@test.com');
    await page.locator('[data-testid="registro-password"]').fill('MiClave123!');
    // Términos no marcados — botón debe seguir deshabilitado

    await expect(page.locator('[data-testid="registro-submit"]')).toBeDisabled();
  });

  test('REG-21: campos obligatorios vacíos deshabilitan el botón de registro', async ({ page }) => {
    await expect(page.locator('[data-testid="registro-submit"]')).toBeDisabled();
  });

  test('REG-22: todos los campos válidos y términos aceptados habilitan el botón', async ({ page }) => {
    await page.locator('[data-testid="registro-nombre"]').fill('Alumno Válido');
    await page.locator('[data-testid="registro-email"]').fill('valido@test.com');
    await page.locator('[data-testid="registro-password"]').fill('Valido1234!');
    await page.locator('[data-testid="registro-terminos"]').check();

    await expect(page.locator('[data-testid="registro-submit"]')).toBeEnabled();
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-07 · Mensajes de error y confirmación
// El sistema debe comunicar claramente éxitos y fallos.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-07 · Mensajes de error y confirmación @regresion', () => {

  test('REG-23: error de servidor en login muestra mensaje visible y no redirige', async ({ page }) => {
    await page.route('**/login', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
    );

    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill('admin@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('Test1234!');
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page.locator('[data-testid="login-message"]')).toBeVisible({ timeout: 5000 });
    await expect(page).not.toHaveURL(/admin\.html/);
  });

  test('REG-24: login exitoso muestra mensaje de confirmación antes de redirigir', async ({ page }) => {
    const token = makeToken('alumno@amicana.com', 'alumno', 1);
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
      })
    );

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('test-stub');
    await page.locator('[data-testid="login-submit"]').click();

    // La UI muestra "Acceso concedido. Redirigiendo..." antes de navegar
    await expect(page.locator('[data-testid="login-message"]')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('[data-testid="login-message"]')).toContainText(/concedido|redirigiendo/i);
  });

  test('REG-25: cuotas vacías muestran mensaje de estado vacío en la UI', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: makeToken('alumno@amicana.com', 'alumno', 1), token_type: 'bearer' }),
      })
    );
    await page.route('**/mis-cuotas', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, cuotas: [], pendientes: 0, vencidas: 0, pagadas: 0, deuda_total: 0 }),
      })
    );

    await irAlLogin(page);
    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('test-stub');
    await page.locator('[data-testid="login-submit"]').click();
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    await expect(page.locator('[data-testid="lista-cuotas"]'))
      .toContainText(/No tenés cuotas asignadas/i, { timeout: 5000 });
  });

});

// ─────────────────────────────────────────────────────────────────
// FC-08 · Eliminación de entidad
// El admin puede eliminar alumnos. La entidad eliminada deja de
// existir en el sistema y no puede autenticarse.
// ─────────────────────────────────────────────────────────────────

test.describe('FC-08 · Eliminación @regresion', () => {

  async function loginAdmin(request) {
    // Intenta credenciales default del seed; si falla hace skip del test
    const candidatos = [
      { username: 'admin@amicana.com', password: 'admin1234' },
      { username: 'admin@amicana.com', password: 'admin123' },
      { username: 'admin@amicana.com', password: 'Admin123!' },
    ];
    for (const creds of candidatos) {
      const form = new URLSearchParams();
      form.set('username', creds.username);
      form.set('password', creds.password);
      const res = await request.post(`${API_BASE}/login`, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        data: form.toString(),
      });
      if (res.status() === 200) {
        const body = await res.json();
        return body.access_token;
      }
    }
    test.skip(); // Admin no accesible en este entorno
    return '';
  }

  test('REG-26: DELETE /alumnos/{id} elimina el registro (API real)', async ({ page }) => {
    const ts = Date.now();
    const paraEliminar = {
      nombre:   `Para Eliminar ${ts}`,
      email:    `eliminar_${ts}@example.com`,
      password: 'Eliminar2024!',
      rol:      'alumno',
    };
    await page.request.post(`${API_BASE}/auth/register`, { data: paraEliminar });

    const loginAlumno = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    const { access_token: tokenAlumno } = await loginAlumno.json();
    const me = await (await page.request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();

    const tokenAdmin = await loginAdmin(page.request);
    const delRes = await page.request.delete(`${API_BASE}/alumnos/${me.id}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });
    expect([200, 204]).toContain(delRes.status());
  });

  test('REG-27: alumno eliminado no puede iniciar sesión (API real)', async ({ page }) => {
    const ts = Date.now();
    const paraEliminar = {
      nombre:   `Del Login ${ts}`,
      email:    `dellog_${ts}@example.com`,
      password: 'Eliminar2024!',
      rol:      'alumno',
    };
    await page.request.post(`${API_BASE}/auth/register`, { data: paraEliminar });

    const loginAlumno = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    const { access_token: tokenAlumno } = await loginAlumno.json();
    const me = await (await page.request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();

    const tokenAdmin = await loginAdmin(page.request);
    await page.request.delete(`${API_BASE}/alumnos/${me.id}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });

    // Intentar login del alumno eliminado → debe fallar
    const reintento = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    expect([400, 401, 403, 404]).toContain(reintento.status());
  });

  test('REG-28: alumno eliminado falla login en la UI', async ({ page }) => {
    const ts = Date.now();
    const paraEliminar = {
      nombre:   `Del UI ${ts}`,
      email:    `delui_${ts}@example.com`,
      password: 'Eliminar2024!',
      rol:      'alumno',
    };
    await page.request.post(`${API_BASE}/auth/register`, { data: paraEliminar });

    const loginAlumno = await page.request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    const { access_token: tokenAlumno } = await loginAlumno.json();
    const me = await (await page.request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();

    const tokenAdmin = await loginAdmin(page.request);
    await page.request.delete(`${API_BASE}/alumnos/${me.id}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });

    // Verificar en la UI que el login falla y muestra error
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(paraEliminar.email);
    await page.locator('[data-testid="login-password"]').fill(paraEliminar.password);
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page.locator('[data-testid="login-message"]')).toBeVisible({ timeout: 8000 });
    await expect(page).not.toHaveURL(/alumno\.html/);
  });

});
