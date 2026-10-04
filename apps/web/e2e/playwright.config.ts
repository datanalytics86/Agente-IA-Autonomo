import { defineConfig } from '@playwright/test'

// Harness de esta ola: sin webServer. El smoke lee dist/index.html.
// El e2e de la DoD (login → aprobar HITL) no se deja en skip; entra con la API.
export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:8080',
  },
})
