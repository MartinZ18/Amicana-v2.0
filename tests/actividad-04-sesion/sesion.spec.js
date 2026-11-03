// @ts-check
/**
 * Actividad 04 – Sesión en cookie httpOnly (E2E contra el backend REAL)
 *
 * Sin mocks: UI real → FastAPI real → MySQL real. Hay que levantar uvicorn con
 * SESSION_COOKIE_SECURE=0 (http plano) y una BD descartable con dos usuarios:
 * un admin y un alumno. Las credenciales llegan por variables de entorno
 * (no hay ninguna fija en el repo):
 *
 *   E2E_ADMIN_EMAIL  E2E_ADMIN_PASSWORD  E2E_ALUMNO_EMAIL  E2E_ALUMNO_PASSWORD
 *
 * Sin esas variables la suite se omite.
 *
 * Qué prueba:
 *   - el login por la UI deja la sesión en una cookie HttpOnly y ningún JWT en
 *     localStorage / sessionStorage;
 *   - las acciones que modifican datos mandan X-CSRF-Token (y no Authorization)
 *     y el backend las acepta;
 *   - recargar conserva la sesión; una sesión inválida vuelve al login;
 *   - el logout cierra la sesión del lado del servidor;
 *   - un alumno no puede usar el panel de admin.
 */
import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;
const ALUMNO_EMAIL = process.env.E2E_ALUMNO_EMAIL;
const ALUMNO_PASSWORD = process.env.E2E_ALUMNO_PASSWORD;

// Un JWT en cualquier parte del valor (suelto, dentro de un JSON o con prefijo): header en base64url empieza con eyJ.
const PARECE_JWT = /eyJ[\w-]+\.[\w-]+\.[\w-]+/;

test.skip(
  !(ADMIN_EMAIL && ADMIN_PASSWORD && ALUMNO_EMAIL && ALUMNO_PASSWORD),
  'Faltan E2E_ADMIN_* / E2E_ALUMNO_*: suite de sesión omitida',
);

async function iniciarSesion(page, email, password) {
  await page.goto('/app/index.html');
  await page.locator('[data-testid="login-email"]').fill(email);
  await page.locator('[data-testid="login-password"]').fill(password);
  await page.locator('[data-testid="login-submit"]').click();
}

/** Valores de localStorage + sessionStorage de la página actual. */
async function valoresDeStorage(page) {
  return page.evaluate(() => {
    const out = [];
    for (const st of [localStorage, sessionStorage]) {
      for (let i = 0; i < st.length; i++) out.push(st.getItem(st.key(i)) || '');
    }
    return out;
  });
}

async function cookiesDeSesion(context) {
  const cookies = await context.cookies();
  return {
    sesion: cookies.find(c => c.name === 'amicana_session'),
    csrf: cookies.find(c => c.name === 'amicana_csrf'),
  };
}

test.describe('Sesión en cookie httpOnly – AMICANA', () => {

  test('SES-01: login de admin por la UI → panel, cookie HttpOnly y ningún JWT en storage', async ({ page, context }) => {
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });
    await expect(page.locator('#userRole')).toHaveText('admin');
    await expect(page.locator('#userName')).toHaveText(ADMIN_EMAIL);

    const { sesion, csrf } = await cookiesDeSesion(context);
    expect(sesion, 'cookie amicana_session').toBeDefined();
    expect(sesion.httpOnly).toBe(true);
    expect(sesion.sameSite).toBe('Lax');
    expect(csrf, 'cookie amicana_csrf').toBeDefined();
    expect(csrf.httpOnly).toBe(false); // la lee JS para el header X-CSRF-Token

    // Ningún valor de storage puede parecer un JWT.
    for (const v of await valoresDeStorage(page)) expect(v).not.toMatch(PARECE_JWT);
    // JS no puede ver la cookie de sesión.
    const visibles = await page.evaluate(() => document.cookie);
    expect(visibles).not.toContain('amicana_session');
    expect(visibles).toContain('amicana_csrf');
  });

  test('SES-02: crear y borrar un aviso (POST y DELETE) manda X-CSRF-Token sin Authorization y se persiste', async ({ page }) => {
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });

    const enviados = [];
    page.on('request', req => {
      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method()) && req.url().includes('/avisos')) {
        enviados.push({ metodo: req.method(), headers: req.headers() });
      }
    });

    const titulo = `Aviso e2e sesión ${Date.now()}`;
    await page.locator('.nav-item', { hasText: 'Avisos' }).first().click();
    await page.getByRole('button', { name: 'Nuevo aviso' }).click();
    await page.locator('#avisoTitulo').fill(titulo);
    await page.locator('#avisoContenido').fill('Creado por el test E2E de sesión');
    const respuesta = page.waitForResponse(r => r.url().endsWith('/avisos') && r.request().method() === 'POST');
    await page.locator('#btnGuardarAviso').click();
    const creada = await respuesta;
    expect(creada.status()).toBe(200);
    // El cuerpo se lee ahora: después de recargar la página el navegador ya no lo conserva.
    const idAviso = (await creada.json()).data.id;
    await expect(page.locator('#avisosMsg')).toContainText('Aviso publicado');
    await expect(page.locator('#tablaAvisos')).toContainText(titulo);

    // Persistido de verdad: sobrevive a una recarga completa.
    await page.reload();
    await page.locator('.nav-item', { hasText: 'Avisos' }).first().click();
    const fila = page.locator('#tablaAvisos tr', { hasText: titulo });
    await expect(fila).toHaveCount(1);

    // Y se borra con DELETE (otro método inseguro) usando el mismo apiFetch que usa la página;
    // el botón Eliminar de la tabla se prueba en xss-eliminar.spec.js.
    const borrado = page.waitForResponse(r => r.url().endsWith(`/avisos/${idAviso}`) && r.request().method() === 'DELETE');
    await page.evaluate(id => apiFetch(`/avisos/${id}`, { method: 'DELETE' }), idAviso);
    expect((await borrado).status()).toBe(200);

    const csrf = (await page.context().cookies()).find(c => c.name === 'amicana_csrf');
    expect(enviados.map(e => e.metodo)).toEqual(['POST', 'DELETE']);
    for (const e of enviados) {
      expect(e.headers['x-csrf-token']).toBe(csrf.value);
      expect(e.headers['authorization']).toBeUndefined();
    }
  });

  test('SES-03: recargar conserva la sesión y una sesión inválida vuelve al login', async ({ page, context }) => {
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });

    await page.reload();
    await expect(page).toHaveURL(/admin\.html/);
    await expect(page.locator('#userRole')).toHaveText('admin');

    // Cookie de sesión corrupta (como una sesión vencida): el 401 del servidor manda al login.
    const { sesion } = await cookiesDeSesion(context);
    await context.addCookies([{ ...sesion, value: 'no.es.valida' }]);
    await page.reload();
    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  test('SES-04: logout vuelve al login y /auth/me da 401 después', async ({ page, context }) => {
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });
    expect((await page.request.get('/auth/me')).status()).toBe(200);

    await page.getByRole('button', { name: 'Salir' }).click();
    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();

    const { sesion, csrf } = await cookiesDeSesion(context);
    expect(sesion).toBeUndefined();
    expect(csrf).toBeUndefined();
    expect((await page.request.get('/auth/me')).status()).toBe(401);

    // Sin sesión, el panel no se queda abierto.
    await page.goto('/app/admin.html');
    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
  });

  test('SES-06: si el logout falla (500) se avisa, se queda en el panel y la sesión sigue activa', async ({ page }) => {
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });

    await page.route('**/auth/logout', route =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'boom' }) })
    );
    const avisos = [];
    page.on('dialog', async d => { avisos.push(d.message()); await d.accept(); });

    await page.getByRole('button', { name: 'Salir' }).click();
    await expect.poll(() => avisos.length).toBe(1);
    expect(avisos[0]).toBe('No se pudo cerrar la sesión. Intentá de nuevo.');

    await expect(page).toHaveURL(/admin\.html/);
    expect((await page.request.get('/auth/me')).status()).toBe(200);
    const { sesion } = await cookiesDeSesion(page.context());
    expect(sesion).toBeDefined();
  });

  test('SES-05: alumno entra a su panel y no puede usar admin.html', async ({ page, context }) => {
    await iniciarSesion(page, ALUMNO_EMAIL, ALUMNO_PASSWORD);
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
    await expect(page.locator('#userName')).toHaveText(ALUMNO_EMAIL);

    const { sesion } = await cookiesDeSesion(context);
    expect(sesion.httpOnly).toBe(true);
    for (const v of await valoresDeStorage(page)) expect(v).not.toMatch(PARECE_JWT);

    // Con el alumno logueado, admin.html lo saca y el login lo devuelve a su panel.
    await page.goto('/app/admin.html');
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
    await expect(page.locator('#userRole')).toHaveCount(0);

    // El backend tampoco le da datos de admin con esa sesión.
    expect((await page.request.get('/alumnos')).status()).toBe(403);

    // Logout del alumno.
    await page.getByTestId('btn-logout').click();
    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
    expect((await page.request.get('/auth/me')).status()).toBe(401);
  });

  test('SES-07: si el login anda pero /auth/me falla, se avisa y el botón se rehabilita (sin redirigir)', async ({ page }) => {
    await page.route('**/auth/me', route =>
      route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'No autenticado' }) })
    );
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);

    await expect(page.locator('#loginMsg')).toContainText('No se pudo iniciar la sesión');
    await expect(page.locator('[data-testid="login-submit"]')).toBeEnabled();
    await expect(page.locator('[data-testid="login-submit"]')).not.toHaveText(/Redirigiendo/);
    // Pasada la demora del redirect normal (700 ms) seguimos en el login.
    await page.waitForTimeout(1200);
    await expect(page).toHaveURL(/index\.html/);
  });

  test('SES-08: el chat de un usuario no pasa al siguiente aunque su sesión haya vencido (401) en vez de cerrarla', async ({ page, context }) => {
    await iniciarSesion(page, ALUMNO_EMAIL, ALUMNO_PASSWORD);
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });

    // El widget guarda el id del chat del alumno.
    await page.evaluate(() => {
      localStorage.setItem('amicana_chat_session', JSON.stringify({ id: 'sess_del_alumno', createdAt: Date.now() }));
      sessionStorage.setItem('gp_perfil_omitido', '1');
    });

    // La sesión vence: sin cookie, la primera llamada autenticada da 401 y manda al login (sin logout explícito).
    await context.clearCookies({ name: 'amicana_session' });
    await page.evaluate(() => apiFetch('/mis-cuotas'));
    await expect(page).toHaveURL(/index\.html/, { timeout: 8000 });
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();

    // Otro usuario entra en el mismo navegador: no hereda el chat anterior.
    await iniciarSesion(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });
    expect(await page.evaluate(() => localStorage.getItem('amicana_chat_session'))).toBeNull();
    expect(await page.evaluate(() => sessionStorage.getItem('gp_perfil_omitido'))).toBeNull();
  });

  test('SES-09: una cookie malformada no rompe la página (leerCookie no lanza)', async ({ page }) => {
    await page.goto('/app/index.html');
    const valor = await page.evaluate(() => {
      document.cookie = 'amicana_csrf=%E0%A4%A; path=/';
      return window.leerCookie('amicana_csrf');
    });
    expect(valor).toBeNull();
  });
});
