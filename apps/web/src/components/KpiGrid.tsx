import {
  DollarSign,
  MessagesSquare,
  Percent,
  Cpu,
  Users,
  Wallet,
} from 'lucide-react'
import { formatClp, formatUsd } from '../lib/format'
import { useAgencyStore } from '../store/useAgencyStore'

export function KpiGrid() {
  const revenueClp = useAgencyStore((s) => s.revenueMonthClp())
  const revenueUsd = useAgencyStore((s) => s.revenueMonthUsd())
  const apiUsd = useAgencyStore((s) => s.apiCostMonthUsd)
  const apiClp = useAgencyStore((s) => s.apiCostMonthClp())
  const rate = useAgencyStore((s) => s.responseRate())
  const pipeline = useAgencyStore((s) => s.pipelineCount())
  const messages = useAgencyStore((s) => s.messagesSentMonth)
  const tokens = useAgencyStore((s) => s.tokensToday)

  const items = [
    {
      label: 'Ingresos del mes',
      value: formatUsd(revenueUsd),
      sub: formatClp(revenueClp),
      icon: DollarSign,
    },
    {
      label: 'Costo API',
      value: formatUsd(apiUsd),
      sub: formatClp(apiClp),
      icon: Wallet,
    },
    {
      label: 'Tasa de respuesta',
      value: `${rate}%`,
      sub: rate < 12 ? 'Bajo umbral HITL 12%' : 'Sobre umbral 12%',
      icon: Percent,
      warn: rate < 12,
    },
    {
      label: 'Leads en pipeline',
      value: String(pipeline),
      sub: 'Excluye cerrados',
      icon: Users,
    },
    {
      label: 'Mensajes del mes',
      value: String(messages),
      sub: 'Envíos simulados',
      icon: MessagesSquare,
    },
    {
      label: 'Tokens hoy',
      value: tokens.toLocaleString('es-CL'),
      sub: 'Demo / estimado',
      icon: Cpu,
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-6">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card"
        >
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
              {item.label}
            </p>
            <item.icon
              className={`h-4 w-4 ${item.warn ? 'text-amber-400' : 'text-accent'}`}
            />
          </div>
          <p className="text-xl font-semibold tracking-tight text-zinc-50 sm:text-2xl">
            {item.value}
          </p>
          <p
            className={`mt-1 text-xs ${item.warn ? 'text-amber-300/90' : 'text-zinc-500'}`}
          >
            {item.sub}
          </p>
        </div>
      ))}
    </div>
  )
}
