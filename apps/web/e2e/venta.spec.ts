import { createHmac } from 'node:crypto'
import { readdir, readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type APIRequestContext } from '@playwright/test'

const here = dirname(fileURLToPath(import.meta.url))

const API = 'http://127.0.0.1:8765'
const MP_SECRET = 'mp-test-secret'
const CAL_SECRET = 'cal-test-secret'

async function csrf(request: APIRequestContext): Promise<string> {
  const state = await request.storageState()
  const token = state.cookies.find((cookie) => cookie.name === 'csrf_token')?.value
  expect(token).toBeTruthy()
  return token ?? ''
}

async function login(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API}/api/auth/login`, {
    data: { email: 'admin@example.com', password: 'clave-de-prueba' },
  })
  expect(response.ok()).toBeTruthy()
  return csrf(request)
}

function calSignature(body: string): string {
  return createHmac('sha256', CAL_SECRET).update(body).digest('hex')
}

function mpSignature(paymentId: string): string {
  const signed = /^[A-Za-z0-9]+$/.test(paymentId) ? paymentId.toLowerCase() : paymentId
  const manifest = `id:${signed};request-id:req-e2e;ts:1700000000;`
  const digest = createHmac('sha256', MP_SECRET).update(manifest).digest('hex')
  return `ts=1700000000,v1=${digest}`
}

test('diagnóstico, agenda, checkout falso, portal y sitio publicado', async ({ page, request }) => {
  const business = 'Ferreteria E2E'
  await page.goto('/diagnostico-gratis')
  const form = page.locator('#diagnostico')
  await form.locator('input[name="business"]').fill(business)
  await form.locator('input[name="email"]').fill('e2e@example.com')
  await form.locator('input[name="commune"]').fill('Ñuñoa')
  await form.locator('select[name="category"]').selectOption('ferreteria')
  await form.locator('input[name="consent"]').check()
  await form.locator('button[type="submit"]').click()
  await expect(page.locator('#diagnostico-ok')).toBeVisible()

  const token = await login(request)
  let leadId = ''
  for (let attempt = 0; attempt < 10 && !leadId; attempt += 1) {
    const leads = await request.get(`${API}/api/leads?q=${encodeURIComponent(business)}`)
    expect(leads.ok()).toBeTruthy()
    const body = (await leads.json()) as { items: { id: string; business: string }[] }
    leadId = body.items.find((item) => item.business === business)?.id ?? ''
  }
  expect(leadId).toBeTruthy()

  const booking = JSON.stringify({ lead_id: leadId, triggerEvent: 'BOOKING_CREATED' })
  const booked = await request.post(`${API}/webhooks/calcom`, {
    data: booking,
    headers: {
      'content-type': 'application/json',
      'x-cal-signature-256': calSignature(booking),
    },
  })
  expect(booked.ok()).toBeTruthy()

  await page.goto(`/checkout/landing_esencial?lead_id=${leadId}`)
  await page.locator('#checkout input[name="terms"]').check()
  await page.locator('#checkout button[type="submit"]').click()
  await page.waitForURL(/\/pago\/fake\//)
  await expect(page.getByText('No se hizo ningún cobro.')).toBeVisible()
  const paymentId = new URL(page.url()).pathname.split('/').filter(Boolean).pop() ?? ''
  expect(paymentId).toBeTruthy()

  const paid = await request.post(`${API}/webhooks/mercadopago`, {
    data: { data: { id: paymentId } },
    headers: {
      'x-signature': mpSignature(paymentId),
      'x-request-id': 'req-e2e',
    },
  })
  expect(paid.ok()).toBeTruthy()

  const projects = await request.get(`${API}/api/projects`, {
    headers: { 'X-CSRF-Token': token },
  })
  expect(projects.ok()).toBeTruthy()
  const listed = (await projects.json()) as { lead_id?: string; portal_token: string; status: string }[]
  const project = listed.find((item) => item.portal_token)
  expect(project?.portal_token).toBeTruthy()
  const portal = project?.portal_token ?? ''

  await page.goto(`/proyecto/shell?token=${portal}`)
  await expect(page.locator('#portal-negocio')).toContainText(business)
  await page.locator('#intake input[name="phone"]').fill('+56911111111')
  await page.locator('#intake textarea[name="services"]').fill('Herramientas y fijaciones')
  await page.locator('#intake button[type="submit"]').click()
  await expect(page.locator('#portal-estado')).toContainText('Guardamos el intake.')

  await page.reload()
  await expect(page.getByRole('link', { name: 'Abrir vista previa' })).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.locator('#aprobar').click()
  await expect(page.locator('#portal-estado')).toContainText('Quedó aprobada')

  const root = resolve(here, 'sites')
  const files = await readdir(root, { recursive: true })
  const html = files.filter((name) => String(name).endsWith('index.html'))
  expect(html.length).toBeGreaterThan(0)
  const texts = await Promise.all(
    html.map((name) => readFile(resolve(root, String(name)), 'utf8')),
  )
  expect(texts.some((text) => text.includes(business) && text.includes('noindex'))).toBeTruthy()
})

test('login y aprobar un HITL de alto valor', async ({ request }) => {
  const created = await request.post(`${API}/api/public/diagnostico`, {
    data: {
      business: 'Clinica E2E',
      email: 'clinica-e2e@example.com',
      commune: 'Providencia',
      category: 'clinica-dental',
      consent: true,
      consent_text: 'Acepto el tratamiento para el diagnóstico gratuito.',
      honeypot: '',
      turnstile_token: '',
    },
  })
  expect(created.status()).toBe(202)
  const leadId = ((await created.json()) as { id: string }).id
  const booking = JSON.stringify({ lead_id: leadId, triggerEvent: 'BOOKING_CREATED' })
  const booked = await request.post(`${API}/webhooks/calcom`, {
    data: booking,
    headers: {
      'content-type': 'application/json',
      'x-cal-signature-256': calSignature(booking),
    },
  })
  expect(booked.ok()).toBeTruthy()
  const checkout = await request.post(`${API}/api/public/checkout`, {
    data: { package_code: 'landing_esencial', lead_id: leadId },
  })
  expect(checkout.status()).toBe(201)

  const token = await login(request)
  const pending = await request.get(`${API}/api/approvals?status=pending`)
  expect(pending.ok()).toBeTruthy()
  const approvals = (await pending.json()) as { id: string; kind: string; lead_id?: string }[]
  const hitl = approvals.find((item) => item.kind === 'deal_alto_valor')
  expect(hitl).toBeTruthy()
  const approved = await request.post(`${API}/api/approvals/${hitl?.id}/approve`, {
    headers: { 'X-CSRF-Token': token },
  })
  expect(approved.ok()).toBeTruthy()
})
