import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAgencyStore } from '../store/useAgencyStore'

export function ActivityChart() {
  const activity = useAgencyStore((s) => s.activity)

  return (
    <div className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Actividad semanal</h2>
        <p className="text-xs text-zinc-500">Leads · mensajes · respuestas (Lun–Dom)</p>
      </div>
      <div className="h-56 w-full min-w-0 sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={activity} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fill: '#71717a', fontSize: 12 }}
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
            <Legend
              wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
              formatter={(v) => <span className="text-zinc-400">{v}</span>}
            />
            <Line
              type="monotone"
              dataKey="leads"
              name="Leads"
              stroke="#2dd4bf"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="mensajes"
              name="Mensajes"
              stroke="#38bdf8"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="respuestas"
              name="Respuestas"
              stroke="#a3e635"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
