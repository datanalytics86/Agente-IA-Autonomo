import { defineConfig } from '@playwright/test'
import { platform } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const engine = resolve(here, '../../../engine')
const site = resolve(here, '../../site')
const win = platform() === 'win32'
const ci = !!process.env.CI
const python =
  process.env.E2E_PYTHON ?? (win ? resolve(engine, '.venv/Scripts/python.exe') : 'python')
const npm = win ? 'npm.cmd' : 'npm'
const quote = (value: string) => `"${value}"`

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  forbidOnly: ci,
  retries: ci ? 1 : 0,
  reporter: ci ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4321',
    // Windows local sigue en Edge. En CI no hay msedge: Playwright usa chromium.
    ...(ci ? {} : { channel: 'msedge' as const }),
  },
  webServer: [
    {
      command: `${quote(python)} ${quote(resolve(here, 'serve_api.py'))}`,
      cwd: engine,
      url: 'http://127.0.0.1:8765/healthz',
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        APP_MODE: 'demo',
        DRY_RUN: 'true',
        OUTREACH_ENABLED: 'false',
        SECRET_KEY: 'e2e-secret-key',
        ADMIN_EMAIL: 'admin@example.com',
        ADMIN_PASSWORD: 'clave-de-prueba',
        PUBLIC_BASE_URL: 'http://127.0.0.1:8765',
        MP_WEBHOOK_SECRET: 'mp-test-secret',
        CALCOM_WEBHOOK_SECRET: 'cal-test-secret',
        TURNSTILE_SECRET_KEY: '',
        CORS_ORIGINS: 'http://127.0.0.1:4321',
        CLIENT_SITES_DIR: resolve(here, 'sites'),
        DATABASE_URL: `sqlite:///${resolve(here, 'e2e.db').replace(/\\/g, '/')}`,
        API_PORT: '8765',
      },
    },
    {
      command: `${npm} run build && ${npm} run preview -- --host 127.0.0.1 --port 4321`,
      cwd: site,
      url: 'http://127.0.0.1:4321',
      reuseExistingServer: false,
      timeout: 180_000,
      env: {
        PUBLIC_API_BASE: 'http://127.0.0.1:8765',
        PUBLIC_BASE_URL: 'http://127.0.0.1:4321',
      },
    },
  ],
})
