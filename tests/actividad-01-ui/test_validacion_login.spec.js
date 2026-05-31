// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Tarea 2 — Validación en vivo en el formulario de registro de AMICANA.
 *
 * Verifica que:
 * - Al tipear un email inválido aparece feedback visual (✗).
 * - El botón "Crear cuenta" queda deshabilitado hasta que todos los campos sean válidos.
 * - Al corregir el email aparece feedback positivo (✓) y el botón se habilita.
 */

async function abrirSeccionRegistro(page) {
    await page.goto('/app/index.html');
    await page.locator('[data-testid="btn-toggle-registro"]').click();
    await expect(page.locator('#registroSection')).toHaveClass(/open/);
}

test.describe('Validación en vivo — Registro @validation', () => {

    // TC-VAL-01: email inválido → badge ✗ y botón deshabilitado
    test('TC-VAL-01: email inválido muestra feedback ✗ y deshabilita botón', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-email"]').fill('no-es-email');

        const badge = page.locator('[data-testid="registro-email-badge"]');
        await expect(badge).toBeVisible();
        await expect(badge).toContainText('✗');

        const btn = page.locator('[data-testid="registro-submit"]');
        await expect(btn).toBeDisabled();
    });

    // TC-VAL-02: email válido → badge ✓
    test('TC-VAL-02: email válido muestra feedback ✓', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-email"]').fill('correo@valido.com');

        const badge = page.locator('[data-testid="registro-email-badge"]');
        await expect(badge).toBeVisible();
        await expect(badge).toContainText('✓');
    });

    // TC-VAL-03: todos los campos válidos + checkbox → botón habilitado
    test('TC-VAL-03: campos válidos completos habilitan el botón Crear cuenta', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-nombre"]').fill('María García');
        await page.locator('[data-testid="registro-email"]').fill('maria@valido.com');
        await page.locator('[data-testid="registro-email"]').dispatchEvent('input');
        await page.locator('[data-testid="registro-password"]').fill('Clave1234');
        await page.locator('[data-testid="registro-password"]').dispatchEvent('input');
        // El checkbox de términos es obligatorio (Tarea 3.4)
        await page.locator('[data-testid="registro-terminos"]').check();

        const btn = page.locator('[data-testid="registro-submit"]');
        await expect(btn).toBeEnabled();
    });

    // TC-VAL-04: password débil (solo letras) → botón deshabilitado
    test('TC-VAL-04: password sin número mantiene botón deshabilitado', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-nombre"]').fill('Alguien');
        await page.locator('[data-testid="registro-email"]').fill('alguien@test.com');
        await page.locator('[data-testid="registro-password"]').fill('soloLetras');

        const btn = page.locator('[data-testid="registro-submit"]');
        await expect(btn).toBeDisabled();
    });

    // TC-VAL-05: password corta → botón deshabilitado
    test('TC-VAL-05: password corta (menos de 8 chars) mantiene botón deshabilitado', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-nombre"]').fill('Alguien');
        await page.locator('[data-testid="registro-email"]').fill('alguien@test.com');
        await page.locator('[data-testid="registro-password"]').fill('ab1');

        const btn = page.locator('[data-testid="registro-submit"]');
        await expect(btn).toBeDisabled();
    });

    // TC-VAL-06: indicador de fuerza de password
    test('TC-VAL-06: indicador de fuerza muestra Fuerte para password completa', async ({ page }) => {
        await abrirSeccionRegistro(page);

        await page.locator('[data-testid="registro-password"]').fill('Clave5678');

        const fuerza = page.locator('[data-testid="pw-fuerza"]');
        await expect(fuerza).toContainText(/Fuerte/i);
    });

});
