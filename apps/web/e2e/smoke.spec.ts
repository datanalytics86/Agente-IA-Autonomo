import { expect, test } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const distIndex = resolve(dirname(fileURLToPath(import.meta.url)), '../dist/index.html')
const DASHBOARD_TITLE = 'Agente IA Autónomo'

test('el HTML del build contiene el título del dashboard', () => {
  // Temporal: si falta el build, no es un skip permanente del e2e de la DoD.
  test.skip(!existsSync(distIndex), 'corre después de npm run build')
  const html = readFileSync(distIndex, 'utf8')
  expect(html).toContain(`<title>${DASHBOARD_TITLE}</title>`)
  expect(html).toMatch(/\/admin\/assets\//)
})
