// @ts-check
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html']],
  use: {
    baseURL: 'http://localhost:8000',
    headless: false,
    trace: 'retain-on-failure',
    screenshot: 'on',
    video: 'on',
  },
  projects: [
    {
      name: 'actividad-01-ui',
      testMatch: '**/actividad-01-ui/**/*.spec.js',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'actividad-02-api-mock',
      testMatch: '**/actividad-02-api-mock/**/*.spec.js',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'actividad-03-regresion',
      testMatch: '**/actividad-03-regresion/**/*.spec.js',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
