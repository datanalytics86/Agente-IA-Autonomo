import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchMetrics } from '../api/metrics'
import { leadStatusLabel } from '../lib/labels'
import { cardClass } from '../lib/ui'
import { QueryState } from './QueryState'

export function FunnelChart() {
  const query = useQuery({ queryKey: ['metrics'], queryFn: fetchMetrics })
  const rows = Object.entries(query.data?.funnel ?? {}).map(([status, value]) => ({
    name: leadStatusLabel(status),
    value,
  }))

  return (
    <section className={cardClass}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Embudo</h2>
        <p className="text-xs text-zinc-500">Conteos de metrics.funnel</p>
      </div>
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={!query.isPending && !query.error && rows.length === 0}
        empty="La API no entregó embudo"
      >
        <div className="h-56 w-full min-w-0 sm:h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, left: -18, bottom: 24 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis
                dataKey="name"
                interval={0}
                angle={-28}
                textAnchor="end"
                height={56}
                tick={{ fill: '#71717a', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#71717a', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#12151a',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 12,
                  fontSize: 12,
                }}
                labelStyle={{ color: '#a1a1aa' }}
              />
              <Bar dataKey="value" name="Leads" fill="#2dd4bf" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </QueryState>
    </section>
  )
}
