import { expect, test, type Locator } from '@playwright/test'

const MIN_PX = 44

async function assertTouchTarget(locator: Locator, label: string): Promise<void> {
  const count = await locator.count()
  expect(count, label).toBeGreaterThan(0)
  for (let index = 0; index < count; index += 1) {
    const link = locator.nth(index)
    await link.scrollIntoViewIfNeeded()
    const box = await link.boundingBox()
    expect(box, `${label} #${index}`).not.toBeNull()
    expect(box!.width, `${label} #${index} ancho`).toBeGreaterThanOrEqual(MIN_PX)
    expect(box!.height, `${label} #${index} alto`).toBeGreaterThanOrEqual(MIN_PX)
  }
}

test('nav y CTA de la landing miden al menos 44 px a 360 px', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Principal' })
  for (const name of ['Inicio', 'Paquetes', 'Diagnóstico', 'Agendar']) {
    await assertTouchTarget(nav.getByRole('link', { name, exact: true }), name)
  }
  await assertTouchTarget(page.getByRole('link', { name: 'Pedir diagnóstico gratis', exact: true }), 'diagnóstico')
  await assertTouchTarget(page.getByRole('link', { name: 'Ir al checkout', exact: true }), 'checkout')
})
