const { chromium } = require('@playwright/test');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const outDir = path.join(__dirname);

  // 1. Login page
  await page.goto('http://localhost:8000/app/index.html');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(outDir, '01_login.png'), fullPage: true });
  console.log('01_login.png OK');

  // 2. Registro section
  await page.goto('http://localhost:8000/app/index.html');
  await page.waitForLoadState('networkidle');
  try {
    await page.locator('[data-testid="btn-toggle-registro"]').click({ timeout: 3000 });
    await page.waitForTimeout(500);
  } catch {}
  await page.screenshot({ path: path.join(outDir, '02_registro.png'), fullPage: true });
  console.log('02_registro.png OK');

  // 3. Registro with invalid email (validation badge)
  await page.goto('http://localhost:8000/app/index.html');
  await page.waitForLoadState('networkidle');
  try {
    await page.locator('[data-testid="btn-toggle-registro"]').click({ timeout: 3000 });
    await page.waitForTimeout(300);
    await page.locator('[data-testid="registro-email"]').fill('no-es-email');
    await page.waitForTimeout(300);
  } catch {}
  await page.screenshot({ path: path.join(outDir, '03_validacion_email_invalido.png'), fullPage: true });
  console.log('03_validacion_email_invalido.png OK');

  // 4. Swagger docs (API overview)
  await page.goto('http://localhost:8000/docs');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, '04_swagger_docs.png'), fullPage: false });
  console.log('04_swagger_docs.png OK');

  // 5. Alumno page
  await page.goto('http://localhost:8000/app/alumno.html');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(outDir, '05_alumno.png'), fullPage: true });
  console.log('05_alumno.png OK');

  // 6. Admin page
  await page.goto('http://localhost:8000/app/admin.html');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(outDir, '06_admin.png'), fullPage: true });
  console.log('06_admin.png OK');

  await browser.close();
  console.log('All screenshots done.');
})();
