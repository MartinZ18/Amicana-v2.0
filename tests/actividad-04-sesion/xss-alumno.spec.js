// @ts-check
/**
 * Actividad 04 – Panel del alumno con datos hostiles (E2E contra el backend REAL)
 *
 * Lo que el personal carga (nombre de curso, concepto de una cuota) se muestra en el panel
 * del alumno: tiene que verse literal, sin ejecutar HTML ni romper los atributos de los
 * botones. Además comprueba que una escritura del alumno (PUT /perfil) lleva X-CSRF-Token.
 *
 * Misma preparación que sesion.spec.js (uvicorn con SESSION_COOKIE_SECURE=0 y BD descartable);
 * usa E2E_ADMIN_* y E2E_ALUMNO_*. Sin ellas se omite.
 *
 * Nota: telefono, dni y email del alumno están validados por el backend (no admiten HTML);
 * el nombre del curso lo carga el personal y sí puede traer cualquier texto.
 */
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const ALUMNO_EMAIL = process.env.E2E_ALUMNO_EMAIL;
const ALUMNO_PASSWORD = process.env.E2E_ALUMNO_PASSWORD;

test.skip(
  !(ADMIN_EMAIL && ADMIN_PASSWORD && ALUMNO_EMAIL && ALUMNO_PASSWORD),
  'Faltan E2E_ADMIN_* / E2E_ALUMNO_*: suite omitida',
);

const CURSO_HOSTIL = `Curso <img src=x onerror="window.__xss=1"> ${Date.now()}`;
let cursoCreado = false;
const CONCEPTO_HOSTIL = 'Cuota "doble" <b>negrita</b> \'simple\'';

/** Login por API (Bearer: no usa las cookies del navegador). */
async function tokenDe(request, email, password) {
  const res = await request.post('/login', { form: { username: email, password } });
  expect(res.status()).toBe(200);
  return (await res.json()).access_token;
}

async function prepararDatos(request) {
  const admin = await tokenDe(request, ADMIN_EMAIL, ADMIN_PASSWORD);
  const alumno = await tokenDe(request, ALUMNO_EMAIL, ALUMNO_PASSWORD);
  const authAdmin = { Authorization: `Bearer ${admin}` };
  const yo = await (await request.get('/auth/me', { headers: { Authorization: `Bearer ${alumno}` } })).json();

  if (!cursoCreado) {
    const curso = await request.post('/cursos', {
      headers: authAdmin,
      data: { nombre: CURSO_HOSTIL, monto_cuota: 1000 },
    });
    expect(curso.status(), await curso.text()).toBe(200);
    const cursoId = (await curso.json()).id ?? (await curso.json()).data?.id;
    const asignar = await request.put(`/alumnos/${yo.id}`, { headers: authAdmin, data: { curso_id: cursoId } });
    expect(asignar.status(), await asignar.text()).toBe(200);
    cursoCreado = true;
  }

  const vence = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
  const cuota = await request.post('/asignar-cuotas', {
    headers: authAdmin,
    data: {
      alumno_id: yo.id,
      cuotas: [{ alumno_id: yo.id, concepto: CONCEPTO_HOSTIL, monto: 1234.5, fecha_vencimiento: vence }],
    },
  });
  expect(cuota.status(), await cuota.text()).toBe(200);
}

async function entrarComoAlumno(page) {
  await page.goto('/app/index.html');
  await page.locator('[data-testid="login-email"]').fill(ALUMNO_EMAIL);
  await page.locator('[data-testid="login-password"]').fill(ALUMNO_PASSWORD);
  await page.locator('[data-testid="login-submit"]').click();
  await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
}

test.describe('Panel del alumno con datos hostiles', () => {

  test.beforeEach(async ({ request }) => {
    await prepararDatos(request);
  });

  test('XSS-03: el curso con HTML se ve literal en la cabecera del perfil y no ejecuta nada', async ({ page }) => {
    await entrarComoAlumno(page);
    await expect(page.locator('#profileMeta')).toContainText(CURSO_HOSTIL);
    expect(await page.evaluate(() => /** @type {any} */ (window).__xss)).toBeUndefined();
    await expect(page.locator('#profileMeta img')).toHaveCount(0);
  });

  test('XSS-04: la cuota con comillas y <b> se ve literal y su botón Pagar abre el modal con el concepto exacto', async ({ page }) => {
    // Sin Mercado Pago real: window.open falso y POST /pagar-cuota interceptado.
    await page.addInitScript(() => {
      window.open = () => /** @type {any} */ ({ location: { href: '' }, close() {} });
    });
    let pedidoPago = null;
    await page.route('**/pagar-cuota/*', route => {
      pedidoPago = route.request();
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ ok: true, init_point: 'https://mp.invalid/checkout', preference_id: 'X' }),
      });
    });

    await entrarComoAlumno(page);
    await page.locator('a.nav-item[onclick*=secCuotas]').click();
    const tarjeta = page.locator('#listaCuotas .cuota-card', { hasText: 'Cuota "doble"' }).first();
    await expect(tarjeta).toBeVisible();
    await expect(tarjeta.locator('.cuota-concepto')).toHaveText(CONCEPTO_HOSTIL);
    await expect(tarjeta.locator('b')).toHaveCount(0);

    await tarjeta.getByRole('button', { name: /Pagar esta cuota/ }).click();
    await expect(page.locator('#modalPagar')).toHaveClass(/open/);
    await expect(page.locator('#modalPagarInfo')).toContainText(CONCEPTO_HOSTIL);
    expect(await page.evaluate(() => cuotaSeleccionada.concepto)).toBe(CONCEPTO_HOSTIL);

    await page.locator('#btnMercadoPago').click();
    await expect.poll(() => pedidoPago !== null).toBe(true);
    expect(pedidoPago.method()).toBe('POST');
    expect(pedidoPago.headers()['x-csrf-token']).toBeTruthy();
  });

  test('XSS-05: guardar el perfil (PUT /perfil) manda X-CSRF-Token igual a la cookie y sin Authorization', async ({ page }) => {
    await entrarComoAlumno(page);
    await page.locator('a.nav-item[onclick*=secPerfil]').click();
    await expect(page.locator('#perfilEmail')).toHaveValue(ALUMNO_EMAIL);
    await page.locator('#perfilTelefono').fill('1155551234');

    const respuesta = page.waitForResponse(r => r.url().endsWith('/perfil') && r.request().method() === 'PUT');
    await page.locator('#secPerfil button[type=submit]').click();
    const r = await respuesta;
    expect(r.status()).toBe(200);

    const csrf = (await page.context().cookies()).find(c => c.name === 'amicana_csrf');
    expect(r.request().headers()['x-csrf-token']).toBe(csrf.value);
    expect(r.request().headers()['authorization']).toBeUndefined();
  });

  test('XSS-06: sin pop-up (window.open devuelve null) el pago muestra un error claro y reactiva el botón', async ({ page }) => {
    await page.addInitScript(() => { window.open = () => null; });
    await page.route('**/pagar-cuota/*', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ ok: true, init_point: 'https://mp.invalid/checkout', preference_id: 'X' }),
    }));

    await entrarComoAlumno(page);
    await page.locator('a.nav-item[onclick*=secCuotas]').click();
    await page.locator('#listaCuotas .cuota-card', { hasText: 'Cuota "doble"' }).first()
      .getByRole('button', { name: /Pagar esta cuota/ }).click();
    await page.locator('#btnMercadoPago').click();

    await expect(page.locator('#modalPagarMsg')).toContainText(/ventana|pop-?up|bloque/i);
    await expect(page.locator('#btnMercadoPago')).toBeEnabled();
    await expect(page.locator('#btnMercadoPago')).toHaveText('Pagar con MercadoPago');
  });
});
