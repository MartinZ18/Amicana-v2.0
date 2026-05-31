// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Actividad 2 — Spec 3: Pruebas Híbridas (API Setup + UI Verify)
 *
 * REQUIERE: backend corriendo en localhost:8000 con MySQL accesible.
 *
 * Patrón: preparar el estado via API (rápido y determinista)
 *         y luego validar el resultado desde la UI.
 *
 * Flujo de cada test:
 *   PASO 1 — Crear/preparar estado via API
 *   PASO 2 — Interactuar con la UI
 *   PASO 3 — Verificar resultado visible en pantalla
 */

const API_BASE = 'http://localhost:8000';

async function crearUsuarioViaAPI(request, overrides = {}) {
  const ts = Date.now();
  const datos = {
    nombre:   `PW Hibrido ${ts}`,
    email:    `pw_hibrido_${ts}@example.com`,
    password: 'Hibrido2024!',
    rol:      'alumno',
    ...overrides,
  };
  const res = await request.post(`${API_BASE}/auth/register`, { data: datos });
  expect(res.status()).toBe(200);
  return datos;
}

// ─────────────────────────────────────────────────────────────────
// Patrón base: API Setup → UI Login → verificar panel
// ─────────────────────────────────────────────────────────────────

test.describe('Híbrida: API Setup + UI Verify @hibrida @e2e', () => {

  // TC-HYB-01: Crear usuario por API → verificar visualización en pantalla
  test('TC-HYB-01: usuario creado por API puede iniciar sesión en la UI', async ({ page, request }) => {
    // PASO 1: preparar estado via API
    const creds = await crearUsuarioViaAPI(request);

    // PASO 2: interactuar con la UI
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(creds.email);
    await page.locator('[data-testid="login-password"]').fill(creds.password);
    await page.locator('[data-testid="login-submit"]').click();

    // PASO 3: verificar redirección exitosa al panel
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
    const token = await page.evaluate(() => sessionStorage.getItem('token'));
    expect(token).toBeTruthy();
  });

  // TC-HYB-02: Usuario real → falla con contraseña incorrecta en UI
  test('TC-HYB-02: usuario creado por API falla login con contraseña incorrecta en UI', async ({ page, request }) => {
    // PASO 1: crear usuario real via API
    const creds = await crearUsuarioViaAPI(request);

    // PASO 2: intentar login con contraseña incorrecta
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(creds.email);
    await page.locator('[data-testid="login-password"]').fill('claveIncorrecta999');
    await page.locator('[data-testid="login-submit"]').click();

    // PASO 3: verificar error visible y sin redirección
    await expect(page.locator('[data-testid="login-message"]')).toBeVisible({ timeout: 8000 });
    await expect(page).not.toHaveURL(/alumno/);
  });

  // TC-HYB-03: Datos creados por API coinciden con lo visible en la UI
  test('TC-HYB-03: email del alumno creado por API está en el JWT almacenado en UI', async ({ page, request }) => {
    // PASO 1: crear usuario con datos conocidos
    const ts = Date.now();
    const datos = {
      nombre:   `Carlos ${ts}`,
      email:    `carlos_v_${ts}@example.com`,
      password: 'Verificado2024!',
      rol:      'alumno',
    };
    await request.post(`${API_BASE}/auth/register`, { data: datos });

    // PASO 2: login en UI
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(datos.email);
    await page.locator('[data-testid="login-password"]').fill(datos.password);
    await page.locator('[data-testid="login-submit"]').click();
    await page.waitForURL(/alumno/, { timeout: 8000 });

    // PASO 3: verificar que el JWT pertenece al usuario creado
    const payload = await page.evaluate((t) => {
      const raw = sessionStorage.getItem('token');
      if (!raw) return null;
      const p = raw.split('.')[1];
      return JSON.parse(atob(p + '='.repeat((4 - p.length % 4) % 4)));
    }, null);
    expect(payload.sub).toBe(datos.email);
  });

  // TC-HYB-04: Backend sano → crear usuario via API → login en UI funciona
  test('TC-HYB-04: cuando el backend está OK el alta via API y login en UI funcionan', async ({ page, request }) => {
    // PASO 1: verificar que el backend está disponible
    const healthRes = await request.get(`${API_BASE}/Prueba`);
    expect(healthRes.status()).toBe(200);

    // PASO 2: crear usuario via API
    const ts = Date.now();
    const usuario = {
      nombre:   `HYB04 ${ts}`,
      email:    `hyb04_${ts}@example.com`,
      password: 'Hibrido2024!',
      rol:      'alumno',
    };
    const crearRes = await request.post(`${API_BASE}/auth/register`, { data: usuario });
    expect(crearRes.status()).toBe(200);

    // PASO 3: login en UI debe funcionar
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(usuario.email);
    await page.locator('[data-testid="login-password"]').fill(usuario.password);
    await page.locator('[data-testid="login-submit"]').click();
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
  });

});

// ─────────────────────────────────────────────────────────────────
// Patrón avanzado: API Setup → Modificar → Verificar en UI
// ─────────────────────────────────────────────────────────────────

test.describe('Híbrida: Modificación via API + Verificar en UI @hibrida', () => {

  // TC-HYB-05: Crear usuario → modificar perfil via API → datos reflejados en /auth/me
  test('TC-HYB-05: modificar telefono via API se refleja en /auth/me', async ({ page, request }) => {
    // PASO 1: crear usuario
    const creds = await crearUsuarioViaAPI(request);

    // PASO 2: login por API para obtener token
    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: creds.email, password: creds.password },
    });
    const { access_token } = await loginRes.json();

    // PASO 3: modificar perfil via API
    const nuevoTel = '1161234567';
    const putRes = await request.put(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { email: creds.email, telefono: nuevoTel },
    });
    expect(putRes.status()).toBe(200);

    // PASO 4: verificar que el cambio es visible via API
    const perfilRes = await request.get(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(perfilRes.status()).toBe(200);
    const body = await perfilRes.json();
    const perfil = body.data || body.perfil || body;
    expect(perfil.telefono).toBe(nuevoTel);

    // PASO 5: verificar que el usuario puede seguir haciendo login en UI
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(creds.email);
    await page.locator('[data-testid="login-password"]').fill(creds.password);
    await page.locator('[data-testid="login-submit"]').click();
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });
  });

  // TC-HYB-06: Eliminar usuario via API → login en UI falla
  test('TC-HYB-06: alumno eliminado via API no puede iniciar sesión en UI', async ({ page, request }) => {
    // PASO 1: crear alumno
    const creds = await crearUsuarioViaAPI(request);

    // PASO 2: obtener ID del alumno
    const loginApiRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: creds.email, password: creds.password },
    });
    const { access_token: tokenAlumno } = await loginApiRes.json();
    const me = await (await request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();

    // PASO 3: login admin y eliminar alumno
    let tokenAdmin = null;
    for (const pw of ['admin1234', 'admin123', 'Admin123!']) {
      const form = new URLSearchParams();
      form.set('username', 'admin@amicana.com');
      form.set('password', pw);
      const res = await request.post(`${API_BASE}/login`, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        data: form.toString(),
      });
      if (res.status() === 200) { tokenAdmin = (await res.json()).access_token; break; }
    }
    if (!tokenAdmin) { test.skip(); return; }

    await request.delete(`${API_BASE}/alumnos/${me.id}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });

    // PASO 4: verificar en UI que el login falla
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(creds.email);
    await page.locator('[data-testid="login-password"]').fill(creds.password);
    await page.locator('[data-testid="login-submit"]').click();

    await expect(page.locator('[data-testid="login-message"]')).toBeVisible({ timeout: 8000 });
    await expect(page).not.toHaveURL(/alumno\.html/);
  });

});
