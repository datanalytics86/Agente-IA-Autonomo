import { Link } from '@tanstack/react-router'
import type { Lead } from '../api/types'
import { cn } from '../lib/cn'
import { formatClp } from '../lib/format'
import { leadStatusLabel } from '../lib/labels'
import { ghostButtonClass } from '../lib/ui'

function statusClass(status: string): string {
  if (status === 'revision') return 'bg-amber-500/10 text-amber-300 ring-amber-500/25'
  if (status === 'perdido' || status === 'opt_out') return 'bg-zinc-500/10 text-zinc-400 ring-zinc-500/20'
  if (status === 'pagado' || status === 'entregado') return 'bg-accent/10 text-accent ring-accent/25'
  return 'bg-white/5 text-zinc-300 ring-white/10'
}

export function LeadsTable({ items }: { items: Lead[] }) {
  if (items.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-white/10 py-12 text-center text-sm text-zinc-500">
        No hay leads en esta página
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {items.map((lead) => (
        <article
          key={lead.id}
          className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="break-words text-base font-semibold text-zinc-50">{lead.business}</h3>
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-[10px] font-medium ring-1',
                    statusClass(lead.status),
                  )}
                >
                  {leadStatusLabel(lead.status)}
                </span>
                {lead.high_value && (
                  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200 ring-1 ring-amber-500/25">
                    High-value
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {lead.category} · {lead.commune}
                {lead.city && lead.city !== lead.commune ? `, ${lead.city}` : ''}
                {lead.paused_from ? ` · pausa desde ${leadStatusLabel(lead.paused_from)}` : ''}
              </p>
            </div>
            <p className="text-sm font-semibold tabular-nums text-zinc-300">
              {typeof lead.estimated_value_clp === 'number'
                ? formatClp(lead.estimated_value_clp)
                : '—'}
            </p>
          </div>
          <p className="mt-2 text-[11px] text-zinc-500">Valor estimado. No es ingreso.</p>
          <div className="mt-4">
            <Link to="/leads/$leadId" params={{ leadId: lead.id }} className={ghostButtonClass}>
              Ver detalle
            </Link>
          </div>
        </article>
      ))}
    </div>
  )
}
