import { useQuery } from '@tanstack/react-query'
import { Cpu, DollarSign, Gauge, Percent, Users, Wallet } from 'lucide-react'
import { fetchMetrics, llmCostUsd, pipelineTotal, revenueClp, tokensToday } from '../api/metrics'
import type { Metrics } from '../api/types'
import { formatClp, formatUsd } from '../lib/format'
import { leadStatusLabel } from '../lib/labels'
import { QueryState } from './QueryState'

function formatRate(value: number): string {
  const pct = Math.abs(value) <= 1 ? value * 100 : value
  return `${new Intl.NumberFormat('es-CL', { maximumFractionDigits: 1 }).format(pct)}%`
}

function rateLines(metrics: Metrics): string {
  const entries = Object.entries(metrics.response_rate_by_channel ?? {})
  if (entries.length === 0) return 'Sin tasas en la API'
  return entries.map(([channel, value]) => `${channel} ${formatRate(value)}`).join(' · ')
}

function quotaLines(metrics: Metrics): string {
  const entries = Object.entries(metrics.quotas ?? {})
  if (entries.length === 0) return 'Sin cupos en la API'
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(' · ')
}

function lowRate(metrics: Metrics): boolean {
  return Object.values(metrics.response_rate_by_channel ?? {}).some((value) => {
    const fraction = Math.abs(value) <= 1 ? value : value / 100
    return fraction < 0.12
  })
}

export function KpiGrid() {
  const query = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 30_000,
  })

  return (
    <QueryState isPending={query.isPending} error={query.error}>
      {query.data ? <Grid metrics={query.data} /> : null}
    </QueryState>
  )
}

function Grid({ metrics }: { metrics: Metrics }) {
  const revenue = revenueClp(metrics)
  const cost = llmCostUsd(metrics)
  const tokens = tokensToday(metrics)
  const pipeline = pipelineTotal(metrics)
  const rates = rateLines(metrics)
  const warn = lowRate(metrics)
  const pipelineText =
    pipeline === null
      ? 'Sin pipeline en la API'
      : Object.entries(metrics.pipeline ?? {})
          .map(([status, count]) => `${leadStatusLabel(status)} ${count}`)
          .join(' · ') || 'Sin etapas'

  const items = [
    {
      label: 'Ingresos del mes',
      value: formatClp(revenue),
      sub: 'revenue_clp · payments',
      icon: DollarSign,
      warn: false,
    },
    {
      label: 'Costo API',
      value: formatUsd(cost),
      sub: 'llm_cost_usd',
      icon: Wallet,
      warn: false,
    },
    {
      label: 'Tasa de respuesta',
      value: warn ? 'Bajo 12%' : 'Por canal',
      sub: rates,
      icon: Percent,
      warn,
    },
    {
      label: 'Leads en pipeline',
      value: pipeline === null ? '—' : String(pipeline),
      sub: pipelineText,
      icon: Users,
      warn: false,
    },
    {
      label: 'Cupos del día',
      value: metrics.quotas ? String(Object.keys(metrics.quotas).length) : '—',
      sub: quotaLines(metrics),
      icon: Gauge,
      warn: false,
    },
    {
      label: 'Tokens hoy',
      value: tokens === null ? '—' : tokens.toLocaleString('es-CL'),
      sub: tokens === null ? 'La API no envió tokens_today' : 'tokens_today',
      icon: Cpu,
      warn: false,
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-6">
      {items.map((item) => (
        <div
          key={item.label}
          className="min-w-0 rounded-2xl border border-white/5 bg-elevated p-4 shadow-card"
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
              {item.label}
            </p>
            <item.icon className={`h-4 w-4 shrink-0 ${item.warn ? 'text-amber-400' : 'text-accent'}`} />
          </div>
          <p className="truncate text-xl font-semibold tracking-tight text-zinc-50 sm:text-2xl">
            {item.value}
          </p>
          <p className={`mt-1 line-clamp-3 text-xs ${item.warn ? 'text-amber-300/90' : 'text-zinc-500'}`}>
            {item.sub}
          </p>
        </div>
      ))}
    </div>
  )
}
