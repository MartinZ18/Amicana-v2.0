// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Actividad 2 — Spec 1: API Testing sobre endpoints reales de AMICANA
 *
 * REQUIERE: backend corriendo en localhost:8000 con MySQL accesible.
 *
 * Cubre:
 *   - Autenticación y registro de usuarios
 *   - Crear usuario por API y verificar su visualización en la UI
 *   - Modificación de datos via API
 *   - Eliminación de entidad via API
 *   - Rutas protegidas (con y sin token)
 */

const API_BASE = 'http://localhost:8000';

let testUser;

test.beforeAll(async ({ request }) => {
  const ts = Date.now();
  testUser = {
    nombre:   `Test API ${ts}`,
    email:    `testapi_${ts}@example.com`,
    password: 'TestPass2024!',
    rol:      'alumno',
  };
  const res = await request.post(`${API_BASE}/auth/register`, { data: testUser });
  expect(res.status()).toBe(200);
});

function loginFormData(username, password) {
  const form = new URLSearchParams();
  form.set('username', username);
  form.set('password', password);
  return { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, data: form.toString() };
}

async function obtenerToken(request) {
  const res = await request.post(`${API_BASE}/login`, loginFormData(testUser.email, testUser.password));
  expect(res.status()).toBe(200);
  const body = await res.json();
  return body.access_token;
}

// ─────────────────────────────────────────────────────────────────
// TC-API-01 · Autenticación
// ─────────────────────────────────────────────────────────────────

test.describe('API: Autenticación @api @smoke', () => {

  test('TC-API-01: POST /login con credenciales válidas devuelve token JWT', async ({ request }) => {
    const response = await request.post(`${API_BASE}/login`, loginFormData(testUser.email, testUser.password));

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('access_token');
    expect(body).toHaveProperty('token_type', 'bearer');
    expect(body.access_token.split('.').length).toBe(3);
  });

  test('TC-API-02: POST /login con credenciales inválidas devuelve error 4xx', async ({ request }) => {
    const response = await request.post(`${API_BASE}/login`,
      loginFormData('noexiste_xyz@test.com', 'WrongPass999!'));

    expect([400, 401, 403]).toContain(response.status());
    const body = await response.json();
    // El backend puede usar 'detail' (FastAPI estándar) o 'mensaje' (convención AMICANA)
    const tieneError = 'detail' in body || 'mensaje' in body;
    expect(tieneError).toBe(true);
  });

});

// ─────────────────────────────────────────────────────────────────
// TC-API-03 · Registro
// ─────────────────────────────────────────────────────────────────

test.describe('API: Registro de usuarios @api', () => {

  test('TC-API-03: POST /auth/register con datos válidos crea la cuenta', async ({ request }) => {
    const ts = Date.now();
    const response = await request.post(`${API_BASE}/auth/register`, {
      data: {
        nombre:   `Nuevo ${ts}`,
        email:    `nuevo_${ts}@example.com`,
        password: 'TestPass2024!',
        rol:      'alumno',
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('ok', true);
  });

  test('TC-API-04: POST /auth/register con email duplicado devuelve error', async ({ request }) => {
    const response = await request.post(`${API_BASE}/auth/register`, {
      data: {
        nombre:   'Duplicado',
        email:    testUser.email,
        password: 'TestPass2024!',
        rol:      'alumno',
      },
    });

    expect([400, 409]).toContain(response.status());
  });

});

// ─────────────────────────────────────────────────────────────────
// TC-API-05 · Crear usuario por API y verificar visualización en UI
// Justificación: valida el ciclo completo de alta — el dato creado
//                via API debe ser visible y funcional en la interfaz.
// ─────────────────────────────────────────────────────────────────

test.describe('API + UI: Crear usuario y verificar visualización @api @smoke', () => {

  test('TC-API-05: alumno creado por API puede autenticarse y su email aparece en el panel', async ({ page, request }) => {
    // Paso 1: crear alumno via API
    const ts = Date.now();
    const usuario = {
      nombre:   `Alumno Visual ${ts}`,
      email:    `visual_${ts}@example.com`,
      password: 'Visual2024!',
      rol:      'alumno',
    };
    const regRes = await request.post(`${API_BASE}/auth/register`, { data: usuario });
    expect(regRes.status()).toBe(200);

    // Paso 2: verificar que /auth/me lo reconoce (visualización via API)
    const loginApiRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: usuario.email, password: usuario.password },
    });
    expect(loginApiRes.status()).toBe(200);
    const { access_token } = await loginApiRes.json();

    const meRes = await request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(meRes.status()).toBe(200);
    const me = await meRes.json();
    expect(me.email).toBe(usuario.email);
    expect(me.nombre).toBe(usuario.nombre);

    // Paso 3: verificar visualización en UI — el login lleva al dashboard
    await page.goto('/app/index.html');
    await page.locator('[data-testid="login-email"]').fill(usuario.email);
    await page.locator('[data-testid="login-password"]').fill(usuario.password);
    await page.locator('[data-testid="login-submit"]').click();
    await expect(page).toHaveURL(/alumno\.html/, { timeout: 8000 });

    // Paso 4: el token en sessionStorage pertenece al usuario creado
    const payload = await page.evaluate(() => {
      const t = sessionStorage.getItem('token');
      if (!t) return null;
      const p = t.split('.')[1];
      return JSON.parse(atob(p + '='.repeat((4 - p.length % 4) % 4)));
    });
    expect(payload).not.toBeNull();
    expect(payload.sub).toBe(usuario.email);
  });

  test('TC-API-06: perfil del alumno creado por API es accesible via /auth/me', async ({ request }) => {
    const ts = Date.now();
    const usuario = {
      nombre:   `Perfil Check ${ts}`,
      email:    `perfil_${ts}@example.com`,
      password: 'Perfil2024!',
      rol:      'alumno',
    };
    await request.post(`${API_BASE}/auth/register`, { data: usuario });

    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: usuario.email, password: usuario.password },
    });
    const { access_token } = await loginRes.json();

    const meRes = await request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(meRes.status()).toBe(200);
    const me = await meRes.json();
    expect(me.nombre).toBe(usuario.nombre);
    expect(me.rol).toBe('alumno');
  });

});

// ─────────────────────────────────────────────────────────────────
// TC-API-07 · Modificación de datos via API
// ─────────────────────────────────────────────────────────────────

test.describe('API: Modificación de perfil @api', () => {

  test('TC-API-07: PUT /perfil actualiza el teléfono del usuario', async ({ request }) => {
    const token = await obtenerToken(request);

    const response = await request.put(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        email:    testUser.email,
        telefono: '1161234567',
      },
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('ok', true);
  });

  test('TC-API-08: /perfil refleja los datos actualizados tras PUT', async ({ request }) => {
    const token = await obtenerToken(request);
    const nuevoTel = `1199${Date.now().toString().slice(-6)}`;

    await request.put(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { email: testUser.email, telefono: nuevoTel },
    });

    const perfilRes = await request.get(`${API_BASE}/perfil`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(perfilRes.status()).toBe(200);
    const body = await perfilRes.json();
    const perfil = body.data || body.perfil || body;
    expect(perfil.telefono).toBe(nuevoTel);
  });

});

// ─────────────────────────────────────────────────────────────────
// TC-API-09 · Eliminación via API (requiere rol admin)
// ─────────────────────────────────────────────────────────────────

async function obtenerTokenAdmin(request) {
  for (const pw of ['admin1234', 'admin123', 'Admin123!']) {
    const res = await request.post(`${API_BASE}/login`,
      loginFormData('admin@amicana.com', pw));
    if (res.status() === 200) return (await res.json()).access_token;
  }
  return null; // admin no disponible → test debe hacer skip
}

test.describe('API: Eliminación de alumnos @api', () => {

  test('TC-API-09: DELETE /alumnos/{id} elimina el alumno (admin)', async ({ request }) => {
    const tokenAdmin = await obtenerTokenAdmin(request);
    if (!tokenAdmin) { test.skip(); return; }

    // Crear alumno de prueba para eliminar
    const ts = Date.now();
    const paraEliminar = {
      nombre:   `Para Eliminar ${ts}`,
      email:    `eliminar_${ts}@example.com`,
      password: 'Eliminar2024!',
      rol:      'alumno',
    };
    await request.post(`${API_BASE}/auth/register`, { data: paraEliminar });

    // Login como el alumno para obtener su ID via /auth/me
    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    const { access_token: tokenAlumno } = await loginRes.json();
    const me = await (await request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();
    const alumnoId = me.id;

    // Eliminar el alumno
    const delRes = await request.delete(`${API_BASE}/alumnos/${alumnoId}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });
    expect([200, 204]).toContain(delRes.status());
  });

  test('TC-API-10: alumno eliminado no puede iniciar sesión', async ({ request }) => {
    const tokenAdmin = await obtenerTokenAdmin(request);
    if (!tokenAdmin) { test.skip(); return; }

    const ts = Date.now();
    const paraEliminar = {
      nombre:   `Del Login ${ts}`,
      email:    `dellog_${ts}@example.com`,
      password: 'Eliminar2024!',
      rol:      'alumno',
    };
    await request.post(`${API_BASE}/auth/register`, { data: paraEliminar });

    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: paraEliminar.email, password: paraEliminar.password },
    });
    const { access_token: tokenAlumno } = await loginRes.json();
    const me = await (await request.get(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAlumno}` },
    })).json();

    await request.delete(`${API_BASE}/alumnos/${me.id}`, {
      headers: { Authorization: `Bearer ${tokenAdmin}` },
    });

    // Intentar login del alumno eliminado → debe fallar
    const reintento = await request.post(`${API_BASE}/login`,
      loginFormData(paraEliminar.email, paraEliminar.password));
    expect([400, 401, 403, 404]).toContain(reintento.status());
  });

});

// ─────────────────────────────────────────────────────────────────
// TC-API-11 · Infraestructura y rutas protegidas
// ─────────────────────────────────────────────────────────────────

test.describe('API: Infraestructura y rutas protegidas @api @smoke', () => {

  test('TC-API-11: GET /Prueba devuelve estado healthy', async ({ request }) => {
    const response = await request.get(`${API_BASE}/Prueba`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('mensaje');
  });

  test('TC-API-12: GET /mis-cuotas sin token devuelve 401', async ({ request }) => {
    const response = await request.get(`${API_BASE}/mis-cuotas`);
    expect([401, 403]).toContain(response.status());
  });

  test('TC-API-13: GET /mis-cuotas con token válido devuelve 200', async ({ request }) => {
    const token = await obtenerToken(request);
    const response = await request.get(`${API_BASE}/mis-cuotas`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('ok', true);
    expect(Array.isArray(body.cuotas)).toBe(true);
  });

});
