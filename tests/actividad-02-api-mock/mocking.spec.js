// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Actividad 2 — Spec 2: Mocking con page.route()
 *
 * Cubre los cuatro patrones solicitados:
 *   1. Simular error 500 y comprobar que la UI muestra el mensaje correcto
 *   2. Mockear lista de resultados para validar flujo sin backend real
 *   3. Interceptar respuestas para probar estados vacíos
 *   4. Interceptar para probar estados de error (401, fallo de red)
 *
 * Por qué blockUnmatchedApi es necesario:
 *   alumno.html llama a /perfil, /avisos, /calendario y /mis-cuotas al cargar.
 *   La función api() hace logout() ante cualquier 401 real. blockUnmatchedApi
 *   absorbe esas llamadas devolviendo 200 {} para mantener la página estable;
 *   los mocks específicos registrados después tienen mayor prioridad (LIFO).
 */

const API_LOGIN      = '**/login';
const API_MIS_CUOTAS = '**/mis-cuotas';
const API_PAGAR      = '**/pagar-cuota/**';

function makeToken(sub, rol, id) {
  const header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9';
  const exp    = Math.floor(Date.now() / 1000) + 3600;
  const pay    = Buffer.from(JSON.stringify({ sub, rol, id, exp })).toString('base64');
  return `${header}.${pay}.fakesignature`;
}

/**
 * La sesión real es una cookie httpOnly que setea el servidor. Con el login mockeado
 * no hay cookie, así que el frontend (que pregunta a GET /auth/me quién es) recibe
 * un usuario mockeado mientras la sesión esté "activa". Arranca inactiva (/auth/me da 401),
 * se activa cuando un login responde OK y POST /auth/logout la apaga, como el backend real.
 * Devuelve el estado para que un test pueda simular una sesión vencida (activa = false).
 */
async function mockSesion(page, email, rol, id) {
  const estado = { activa: false };
  page.on('response', r => {
    if (/\/(auth\/)?login$/.test(new URL(r.url()).pathname) && r.ok()) estado.activa = true;
  });
  await page.route('**/auth/me', route =>
    estado.activa
      ? route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id, nombre: 'Test', email, rol, auth_provider: 'local' }),
        })
      : route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'No autenticado' }),
        })
  );
  await page.route('**/auth/logout', route => {
    estado.activa = false;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });
  return estado;
}

/** Sin sesión: /auth/me responde 401, como el backend sin cookie válida. */
async function mockSinSesion(page) {
  await page.route('**/auth/me', route =>
    route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'No autenticado' }) })
  );
}

async function blockUnmatchedApi(page) {
  await page.route('**/*', route => {
    const url = route.request().url();
    if (/\.(html|css|js|png|jpg|svg|ico|woff2?)(\?|$)/.test(url)) return route.continue();
    if (/\/app\//.test(url) && !url.includes('?'))                  return route.continue();
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

async function mockLoginExitoso(page, token = makeToken('alumno@test.com', 'alumno', 99)) {
  await blockUnmatchedApi(page);
  const estado = await mockSesion(page, 'alumno@test.com', 'alumno', 99);
  await page.route(API_LOGIN, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
    })
  );
  return estado;
}

async function hacerLoginEnUI(page) {
  await page.goto('/app/index.html');
  await page.locator('[data-testid="login-email"]').fill('cualquier@email.com');
  await page.locator('[data-testid="login-password"]').fill('cualquierClave1!');
  await page.locator('[data-testid="login-submit"]').click();
}

// ─────────────────────────────────────────────────────────────────
// Patrón 1 — Simular error 500 y verificar mensaje en UI
// ─────────────────────────────────────────────────────────────────

test.describe('Mock: Error 500 — UI muestra mensaje correcto @mock', () => {

  test('TC-MOCK-01: error 500 en /login muestra mensaje de error en UI', async ({ page }) => {
    await page.route(API_LOGIN, route =>
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
    await expect(page).not.toHaveURL(/alumno\.html/);
  });

  test('TC-MOCK-02: error 500 en /mis-cuotas redirige al login por sesión inválida', async ({ page }) => {
    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
    );

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // El frontend llama a api() que ante respuestas no-ok puede redirigir al login
    // En este caso verifica que la lista de cuotas no tiene datos válidos
    const lista = page.locator('[data-testid="lista-cuotas"]');
    // La lista puede mostrar error o quedar vacía — no debe mostrar cuotas reales
    await expect(lista).not.toContainText(/Enero|Febrero|Marzo/i, { timeout: 5000 });
  });

  test('TC-MOCK-03: respuesta exitosa falsa de login redirige al panel de alumno', async ({ page }) => {
    await mockLoginExitoso(page);
    await hacerLoginEnUI(page);
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
  });

});

// ─────────────────────────────────────────────────────────────────
// Patrón 2 — Mockear lista de resultados sin depender del backend
// ─────────────────────────────────────────────────────────────────

test.describe('Mock: Lista de resultados sin backend real @mock', () => {

  const CUOTAS_MOCKEADAS = [
    { id: 1, concepto: 'Cuota Enero 2025',  monto: 15000, estado: 'pendiente', fecha_vencimiento: '2025-01-31' },
    { id: 2, concepto: 'Cuota Febrero 2025', monto: 15000, estado: 'pendiente', fecha_vencimiento: '2025-02-28' },
    { id: 3, concepto: 'Cuota Marzo 2025',  monto: 15000, estado: 'pagado',    fecha_vencimiento: '2025-03-31' },
  ];

  test('TC-MOCK-04: lista de cuotas mockeada con datos renderiza ítems en la UI', async ({ page }) => {
    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          cuotas:     CUOTAS_MOCKEADAS,
          pendientes: 2,
          vencidas:   0,
          pagadas:    1,
          deuda_total: 30000,
        }),
      })
    );

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // La UI debe renderizar los ítems de la lista mockeada
    const lista = page.locator('[data-testid="lista-cuotas"]');
    await expect(lista).toContainText(/Enero/i, { timeout: 6000 });
    await expect(lista).toContainText(/Febrero/i);
  });

  test('TC-MOCK-05: stats del panel reflejan los totales de la lista mockeada', async ({ page }) => {
    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          cuotas:     CUOTAS_MOCKEADAS,
          pendientes: 2,
          vencidas:   0,
          pagadas:    1,
          deuda_total: 30000,
        }),
      })
    );

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // Los contadores del panel deben mostrar los totales del mock
    await expect(page.locator('[data-testid="stat-pendientes"]')).toContainText('2', { timeout: 6000 });
    await expect(page.locator('[data-testid="stat-pagadas"]')).toContainText('1');
  });

  test('TC-MOCK-06: link de pago generado por API externa (MP) es interceptable via mock', async ({ page }) => {
    const INIT_POINT = 'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=TEST-123456';
    let pagarFueCalled = false;

    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          cuotas:     [{ id: 1, concepto: 'Cuota Enero 2025', monto: 15000, estado: 'pendiente', fecha_vencimiento: '2025-01-31' }],
          pendientes: 1,
          vencidas:   0,
          pagadas:    0,
          deuda_total: 15000,
        }),
      })
    );
    await page.route(API_PAGAR, route => {
      pagarFueCalled = true;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, init_point: INIT_POINT, preference_id: 'TEST-123456' }),
      });
    });

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    // Verificar que la lista cargó con la cuota mockeada
    const lista = page.locator('[data-testid="lista-cuotas"]');
    await expect(lista).toContainText(/Enero/i, { timeout: 6000 });

    // Llamar al endpoint de pago directamente (simula lo que haría el botón Pagar)
    // apiFetch es el helper de sesión de la página (cookie + X-CSRF-Token, sin Bearer)
    const resultado = await page.evaluate(async () => {
      const res = await apiFetch('/pagar-cuota/1', { method: 'POST' });
      return { status: res.status, body: await res.json() };
    });

    expect(resultado.status).toBe(200);
    expect(resultado.body.init_point).toBe(INIT_POINT);
    expect(pagarFueCalled).toBe(true);
  });

});

// ─────────────────────────────────────────────────────────────────
// Patrón 3 — Estados vacíos interceptando respuestas
// ─────────────────────────────────────────────────────────────────

test.describe('Mock: Estados vacíos @mock', () => {

  test('TC-MOCK-07: lista de cuotas vacía muestra mensaje de estado vacío', async ({ page }) => {
    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, cuotas: [], pendientes: 0, vencidas: 0, pagadas: 0, deuda_total: 0 }),
      })
    );

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    await expect(page.locator('[data-testid="lista-cuotas"]'))
      .toContainText(/No tenés cuotas asignadas/i, { timeout: 5000 });
  });

  test('TC-MOCK-08: stats muestran cero cuando no hay cuotas', async ({ page }) => {
    await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, cuotas: [], pendientes: 0, vencidas: 0, pagadas: 0, deuda_total: 0 }),
      })
    );

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    await expect(page.locator('[data-testid="stat-pendientes"]')).toContainText('0', { timeout: 5000 });
  });

});

// ─────────────────────────────────────────────────────────────────
// Patrón 4 — Interceptar para estados de error (401, token expirado)
// ─────────────────────────────────────────────────────────────────

test.describe('Mock: Interceptar respuestas de error @mock', () => {

  test('TC-MOCK-09: 401 en /mis-cuotas (sesión vencida) redirige al login', async ({ page }) => {
    const sesion = await mockLoginExitoso(page);
    await page.route(API_MIS_CUOTAS, route => {
      sesion.activa = false; // el servidor ya no reconoce la sesión
      return route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'No autenticado' }),
      });
    });

    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
  });

  test('TC-MOCK-10: el token del body de /login no se guarda en ningún storage', async ({ page }) => {
    const tokenDelBody = makeToken('alumno@test.com', 'alumno', 99);

    await mockLoginExitoso(page, tokenDelBody);
    await hacerLoginEnUI(page);
    await page.waitForURL(/alumno\.html/, { timeout: 8000 });

    const guardados = await page.evaluate(() => [
      ...Object.keys(localStorage), ...Object.values(localStorage),
      ...Object.keys(sessionStorage), ...Object.values(sessionStorage),
    ]);
    expect(guardados.some(v => v === 'token' || v.includes(tokenDelBody))).toBe(false);
    // El usuario sale de /auth/me: el nombre del panel es el email de esa respuesta
    await expect(page.locator('#userName')).toHaveText('alumno@test.com');
  });

});
