import { afterEach, describe, expect, it, vi } from 'vitest'
import { INITIAL_LEADS } from '../lib/mock'
import { fetchMetrics, llmCostUsd, revenueClp, tokensToday } from './metrics'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cliente de métricas', () => {
  it('iguala ingresos, costo y tokens al JSON, sin suma mágica', async () => {
    const payload = {
      revenue_clp: 125_000,
      llm_cost_usd: 1.25,
      tokens_today: 42,
      funnel: { cerrado: 9, agendado: 3, perdido: 4 },
    }
    const fetchMock = vi.fn(async () => json(payload))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('document', { cookie: 'csrf_token=no-va-en-get' })

    const metrics = await fetchMetrics()
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/metrics',
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBeNull()
    expect(revenueClp(metrics)).toBe(payload.revenue_clp)
    expect(revenueClp(metrics)).not.toBe(payload.revenue_clp + 890_000)
    expect(llmCostUsd(metrics)).toBe(1.25)
    expect(tokensToday(metrics)).toBe(42)

    const inventado = INITIAL_LEADS.filter(
      (lead) => lead.status === 'cerrado' || lead.status === 'agendado',
    ).reduce((sum, lead) => sum + lead.estimatedValueClp, 0)
    expect(inventado).toBeGreaterThan(0)
    expect(revenueClp(metrics)).not.toBe(inventado)
    expect(revenueClp(metrics)).not.toBe(inventado + 890_000)
  })

  it('no convierte un embudo con cerrado en ingresos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json({
          revenue_clp: 0,
          llm_cost_usd: 0,
          tokens_today: 0,
          funnel: { cerrado: 2, agendado: 1 },
        }),
      ),
    )
    const metrics = await fetchMetrics()
    expect(revenueClp(metrics)).toBe(0)
    expect(llmCostUsd(metrics)).toBe(0)
    expect(tokensToday(metrics)).toBe(0)
  })
})
