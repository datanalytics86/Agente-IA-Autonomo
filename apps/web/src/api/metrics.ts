import { ApiError, apiFetch } from './http'
import type { Metrics } from './types'

/** Solo el campo revenue_clp. No suma estados ni un monto fijo. */
export function revenueClp(metrics: Pick<Metrics, 'revenue_clp'>): number {
  return metrics.revenue_clp
}

export function llmCostUsd(metrics: Pick<Metrics, 'llm_cost_usd'>): number {
  return metrics.llm_cost_usd
}

export function tokensToday(metrics: Pick<Metrics, 'tokens_today'>): number | null {
  return typeof metrics.tokens_today === 'number' ? metrics.tokens_today : null
}

export function pipelineTotal(metrics: Pick<Metrics, 'pipeline'>): number | null {
  if (!metrics.pipeline) return null
  return Object.values(metrics.pipeline).reduce((sum, value) => sum + value, 0)
}

export async function fetchMetrics(): Promise<Metrics> {
  const data = await apiFetch<Metrics>('/api/metrics')
  if (!data || typeof data.revenue_clp !== 'number' || typeof data.llm_cost_usd !== 'number') {
    throw new ApiError(
      200,
      'La respuesta de métricas no trae revenue_clp y llm_cost_usd',
      'invalid_shape',
    )
  }
  return data
}
