// @ts-check
/**
 * Actividad 04 – Botones "Eliminar" del panel admin con datos de usuario (E2E contra el backend REAL)
 *
 * Los botones Eliminar armaban el onclick con JSON.stringify(texto) dentro de un atributo
 * entre comillas dobles: la comilla inicial cerraba el atributo, el botón no abría el modal
 * y un nombre como  x" onmouseover="..." y="  inyectaba un manejador de eventos (XSS almacenado).
 *
 * Misma preparación que sesion.spec.js (uvicorn con SESSION_COOKIE_SECURE=0 y BD descartable);
 * usa E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD. Sin ellas se omite.
 */
import { test, expect } from '@playwright/test';
import { claveDePrueba } from '../helpers/claves.js';

const CLAVE = claveDePrueba();

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD;

test.skip(!(ADMIN_EMAIL && ADMIN_PASSWORD), 'Faltan E2E_ADMIN_*: suite omitida');

const NOMBRE_HOSTIL = 'x" onmouseover="window.__xss=1" y="';

async function entrarComoAdmin(page) {
  await page.goto('/app/index.html');
  await page.locator('[data-testid="login-email"]').fill(ADMIN_EMAIL);
  await page.locator('[data-testid="login-password"]').fill(ADMIN_PASSWORD);
  await page.locator('[data-testid="login-submit"]').click();
  await expect(page).toHaveURL(/admin\.html/, { timeout: 8000 });
}

test.describe('Eliminar con datos hostiles – panel admin', () => {

  test('XSS-01: alumno con comillas en el nombre no inyecta eventos y su Eliminar abre el modal', async ({ page, request }) => {
    const ts = Date.now();
    const reg = await request.post('/auth/register', {
      data: { nombre: NOMBRE_HOSTIL, email: `xss_${ts}@example.com`, password: CLAVE, rol: 'alumno' },
    });
    expect(reg.status()).toBe(200);

    await entrarComoAdmin(page);
    await page.locator('.nav-item', { hasText: 'Alumnos' }).first().click();
    // La tabla pagina de a 25: se filtra por el email para no depender de cuántos alumnos haya.
    await page.locator('#searchAlumno').fill(`xss_${ts}@example.com`);

    const fila = page.locator('#tablaAlumnos tr', { hasText: `xss_${ts}@example.com` });
    await expect(fila).toHaveCount(1);
    const eliminar = fila.getByRole('button', { name: 'Eliminar' });
    await eliminar.hover();
    await eliminar.click();

    // El modal de confirmación se abre y muestra el nombre literal
    await expect(page.locator('#modalConfirmar')).toHaveClass(/open/);
    await expect(page.locator('#confirmarMsg')).toContainText(NOMBRE_HOSTIL);
    // Ningún manejador inyectado se ejecutó
    expect(await page.evaluate(() => /** @type {any} */ (window).__xss)).toBeUndefined();
  });

  test('XSS-02: el botón Eliminar de un aviso abre el modal de confirmación', async ({ page }) => {
    await entrarComoAdmin(page);
    const titulo = `Aviso "con comillas" ${Date.now()}`;
    await page.locator('.nav-item', { hasText: 'Avisos' }).first().click();
    await page.getByRole('button', { name: 'Nuevo aviso' }).click();
    await page.locator('#avisoTitulo').fill(titulo);
    await page.locator('#avisoContenido').fill('Prueba del botón Eliminar');
    await page.locator('#btnGuardarAviso').click();
    const fila = page.locator('#tablaAvisos tr', { hasText: titulo });
    await expect(fila).toHaveCount(1);

    await fila.getByRole('button', { name: 'Eliminar' }).click();
    await expect(page.locator('#modalConfirmar')).toHaveClass(/open/);
    await expect(page.locator('#confirmarMsg')).toContainText(titulo);

    // Confirmar borra el aviso (DELETE con CSRF)
    const borrado = page.waitForResponse(r => r.request().method() === 'DELETE' && /\/avisos\/\d+$/.test(r.url()));
    await page.locator('#btnConfirmarEliminar').click();
    expect((await borrado).status()).toBe(200);
    await expect(page.locator('#tablaAvisos')).not.toContainText(titulo);
  });
});
