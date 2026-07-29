import { toast } from 'sonner'
import { formatClp } from '../lib/format'
import { cn } from '../lib/cn'
import { STATUS_LABELS, type LeadStatus } from '../lib/types'
import { useAgencyStore } from '../store/useAgencyStore'

const BADGE: Partial<Record<LeadStatus, string>> = {
  nuevo: 'bg-sky-500/10 text-sky-300 ring-sky-500/20',
  diagnosticado: 'bg-violet-500/10 text-violet-300 ring-violet-500/20',
  landing: 'bg-cyan-500/10 text-cyan-300 ring-cyan-500/20',
  video: 'bg-teal-500/10 text-teal-300 ring-teal-500/20',
  pitch_listo: 'bg-lime-500/10 text-lime-300 ring-lime-500/20',
  enviado: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/20',
  respondio: 'bg-green-500/10 text-green-300 ring-green-500/20',
  agendado: 'bg-accent/10 text-accent ring-accent/25',
  cerrado: 'bg-zinc-500/10 text-zinc-400 ring-zinc-500/20',
  revision: 'bg-amber-500/10 text-amber-300 ring-amber-500/25',
}

export function LeadsTable({
  filterStatus,
}: {
  filterStatus?: LeadStatus | 'all'
}) {
  const leads = useAgencyStore((s) => s.leads)
  const advanceLead = useAgencyStore((s) => s.advanceLead)
  const approveLead = useAgencyStore((s) => s.approveLead)
  const rejectLead = useAgencyStore((s) => s.rejectLead)
  const online = useAgencyStore((s) => s.systemOnline)

  const filtered =
    !filterStatus || filterStatus === 'all'
      ? leads
      : leads.filter((l) => l.status === filterStatus)

  return (
    <div className="space-y-3">
      {filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-white/10 py-12 text-center text-sm text-zinc-500">
          No hay leads con ese filtro
        </div>
      )}
      {filtered.map((lead) => (
        <article
          key={lead.id}
          className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-zinc-50">{lead.business}</h3>
                <span
                  className={cn(
                    'rounded-full px-2 py-0.5 text-[10px] font-medium ring-1',
                    BADGE[lead.status],
                  )}
                >
                  {STATUS_LABELS[lead.status]}
                </span>
                {lead.highValue && (
                  <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200 ring-1 ring-amber-500/25">
                    High-value
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {lead.category} · {lead.commune}
                {lead.city !== lead.commune ? `, ${lead.city}` : ''} · rating{' '}
                {lead.rating.toFixed(1)} ({lead.reviews} reseñas)
                {lead.hasWebsite
                  ? ` · web ${lead.websiteYear ?? 'sí'}`
                  : ' · sin web'}
              </p>
            </div>
            <p className="text-sm font-semibold tabular-nums text-accent">
              {formatClp(lead.estimatedValueClp)}
            </p>
          </div>

          {lead.diagnosis && (
            <p className="mt-3 text-sm leading-relaxed text-zinc-300">
              <span className="font-medium text-zinc-400">Diagnóstico: </span>
              {lead.diagnosis}
            </p>
          )}
          {lead.pitch && (
            <p className="mt-2 rounded-xl border border-white/5 bg-surface/60 p-3 text-sm leading-relaxed text-zinc-400">
              <span className="font-medium text-zinc-300">Pitch: </span>
              {lead.pitch}
            </p>
          )}
          {lead.reason && (
            <p className="mt-2 text-xs text-amber-200/90">{lead.reason}</p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {lead.status === 'revision' ? (
              <>
                <button
                  type="button"
                  disabled={!online}
                  onClick={() => {
                    approveLead(lead.id)
                    toast.success('Deal aprobado', {
                      description: `${lead.business} → enviado`,
                    })
                  }}
                  className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-surface hover:bg-accent-soft disabled:opacity-40"
                >
                  Aprobar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    rejectLead(lead.id)
                    toast.message('Lead descartado', {
                      description: lead.business,
                    })
                  }}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-white/5"
                >
                  Descartar
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  disabled={!online || lead.status === 'cerrado'}
                  onClick={() => {
                    advanceLead(lead.id)
                    toast.success('Lead avanzado', { description: lead.business })
                  }}
                  className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-semibold text-zinc-100 hover:bg-white/15 disabled:opacity-40"
                >
                  Avanzar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    rejectLead(lead.id)
                    toast.message('Lead descartado', { description: lead.business })
                  }}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-400 hover:bg-white/5"
                >
                  Descartar
                </button>
              </>
            )}
          </div>
        </article>
      ))}
    </div>
  )
}
