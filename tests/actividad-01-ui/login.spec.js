// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Actividad 1 — Flujo Funcional Crítico: Login en AMICANA
 *
 * El frontend llama a POST /login (form-encoded, no JSON).
 * Ante cualquier respuesta que no sea JSON válido lanza un catch
 * con "Error de conexión: ...", por eso TODOS los tests que mockean
 * el endpoint también necesitan blockUnmatchedApi() para que el
 * servidor real no responda con HTML de error antes que el mock.
 *
 * Regla LIFO de Playwright:
 *   blockUnmatchedApi() se registra PRIMERO (menor precedencia).
 *   El mock de /login se registra DESPUÉS (mayor precedencia).
 */

// ── Helpers ───────────────────────────────────────────────────────

/**
 * La sesión real vive en una cookie httpOnly que el servidor setea en el login.
 * Con el login mockeado no hay cookie, así que el rol (que el frontend pide a
 * GET /auth/me) también se mockea. El body de /login sigue trayendo access_token
 * para clientes de API, pero el frontend tiene que ignorarlo.
 */
async function mockSesion(page, email, rol, id) {
  await page.route('**/auth/me', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ id, nombre: 'Test', email, rol, auth_provider: 'local' }),
    })
  );
}

/**
 * Absorbe cualquier fetch de API sin mock específico → devuelve 200 {}.
 * Deja pasar archivos estáticos y la carpeta /app/ (páginas HTML del frontend).
 * REGISTRAR SIEMPRE PRIMERO; los mocks específicos van después.
 */
async function blockUnmatchedApi(page) {
  await page.route('**/*', route => {
    const url = route.request().url();
    if (/\.(html|css|js|png|jpg|svg|ico|woff2?)(\?|$)/.test(url)) return route.continue();
    if (/\/app\//.test(url) && !url.includes('?'))                 return route.continue();
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

// ─────────────────────────────────────────────────────────────────
// Suite: Login en AMICANA
// ─────────────────────────────────────────────────────────────────

test.describe('Login – AMICANA @smoke @critical', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/app/index.html');
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  // TC-01: Login válido con rol admin → redirige a admin.html
  test('TC-01: login exitoso con admin redirige a admin.html @smoke', async ({ page }) => {
    const token = 'aaaa.bbbb.cccc'; // el frontend no debe guardarlo

    await blockUnmatchedApi(page);
    await mockSesion(page, 'admin@amicana.com', 'admin', 1);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
      })
    );

    await page.locator('[data-testid="login-email"]').fill('admin@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('playwright-test-stub');
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page).toHaveURL(/admin\.html/, { timeout: 6000 });

    // El token del body NO se guarda en ningún storage (la sesión va en cookie httpOnly)
    const guardados = await page.evaluate(() => [
      ...Object.values(localStorage),
      ...Object.values(sessionStorage),
    ]);
    expect(guardados.some(v => v.includes(token))).toBe(false);
    expect(await page.evaluate(() => sessionStorage.getItem('token'))).toBeNull();
    expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
  });

  // TC-02: Login válido con rol alumno → redirige a alumno.html
  test('TC-02: login exitoso con alumno redirige a alumno.html @smoke', async ({ page }) => {
    const token = 'aaaa.bbbb.cccc';

    await blockUnmatchedApi(page);
    await mockSesion(page, 'alumno@amicana.com', 'alumno', 5);
    await page.route('**/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: token, token_type: 'bearer' }),
      })
    );

    await page.locator('[data-testid="login-email"]').fill('alumno@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('playwright-test-stub');
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page).toHaveURL(/alumno\.html/, { timeout: 6000 });
  });

  // TC-03: Contraseña incorrecta → error visible, URL no cambia
  test('TC-03: contraseña incorrecta muestra error y no redirige @regression', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Contraseña incorrecta' }),
      })
    );

    await page.locator('[data-testid="login-email"]').fill('admin@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('claveIncorrecta999');
    await page.locator('[data-testid="login-submit"]').click();

    const msg = page.locator('[data-testid="login-message"]');
    await expect(msg).toBeVisible();
    await expect(msg).toContainText(/incorrecta/i);
    await expect(page).not.toHaveURL(/admin\.html/);
  });

  // TC-04: Usuario inexistente → error visible
  test('TC-04: usuario inexistente muestra error de credenciales @regression', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Usuario no encontrado' }),
      })
    );

    await page.locator('[data-testid="login-email"]').fill('noexiste@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('playwright-test-stub');
    await page.locator('[data-testid="login-submit"]').click();

    const msg = page.locator('[data-testid="login-message"]');
    await expect(msg).toBeVisible();
    await expect(msg).toContainText(/no encontrado/i);
    await expect(page).not.toHaveURL(/admin\.html/);
  });

  // TC-05: Campos vacíos — el form tiene novalidate, el fetch se hace igual,
  //        pero validity.valueMissing es true (campo requerido sin valor)
  test('TC-05: campos vacíos — validity.valueMissing es true @regression', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Credenciales incorrectas' }),
      })
    );

    await page.locator('[data-testid="login-submit"]').click();

    const emailInput = page.locator('[data-testid="login-email"]');
    const valueMissing = await emailInput.evaluate(el => el.validity.valueMissing);
    expect(valueMissing).toBe(true);

    // La UI muestra error (del backend o catch del frontend)
    await expect(page.locator('[data-testid="login-message"]')).toBeVisible();
  });

  // TC-06: Error 500 del servidor → UI muestra error de conexión, no redirige
  test('TC-06: error 500 del servidor muestra mensaje de error, no redirige @regression', async ({ page }) => {
    await blockUnmatchedApi(page);
    await page.route('**/login', route =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
    );

    await page.locator('[data-testid="login-email"]').fill('admin@amicana.com');
    await page.locator('[data-testid="login-password"]').fill('playwright-test-stub');
    await page.locator('[data-testid="login-submit"]').click();

    const msg = page.locator('[data-testid="login-message"]');
    await expect(msg).toBeVisible();
    await expect(page).not.toHaveURL(/admin\.html/);
  });

});

