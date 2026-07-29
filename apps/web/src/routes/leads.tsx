import { createFileRoute } from '@tanstack/react-router'
import { useMemo, useState } from 'react'
import { LeadsTable } from '../components/LeadsTable'
import { STATUS_LABELS, type LeadStatus } from '../lib/types'
import { useAgencyStore } from '../store/useAgencyStore'
import { cn } from '../lib/cn'

type Search = { status?: LeadStatus | 'all' }

export const Route = createFileRoute('/leads')({
  validateSearch: (search: Record<string, unknown>): Search => {
    const s = search.status
    if (typeof s === 'string' && (s === 'all' || s in STATUS_LABELS)) {
      return { status: s as LeadStatus | 'all' }
    }
    return { status: 'all' }
  },
  component: LeadsPage,
})

const FILTERS: Array<LeadStatus | 'all'> = [
  'all',
  'nuevo',
  'diagnosticado',
  'landing',
  'video',
  'pitch_listo',
  'enviado',
  'respondio',
  'agendado',
  'revision',
  'cerrado',
]

function LeadsPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const leads = useAgencyStore((s) => s.leads)
  const [local, setLocal] = useState<LeadStatus | 'all'>(search.status ?? 'all')

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: leads.length }
    for (const l of leads) c[l.status] = (c[l.status] || 0) + 1
    return c
  }, [leads])

  const active = search.status ?? local

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Leads</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Pipeline comercial · {leads.length} total · filtros por status
        </p>
      </header>

      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {FILTERS.map((f) => {
          const label = f === 'all' ? 'Todos' : STATUS_LABELS[f]
          const n = counts[f] ?? 0
          const isActive = active === f
          return (
            <button
              key={f}
              type="button"
              onClick={() => {
                setLocal(f)
                navigate({ search: { status: f } })
              }}
              className={cn(
                'shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition',
                isActive
                  ? 'bg-accent/15 text-accent ring-accent/30'
                  : 'bg-elevated text-zinc-400 ring-white/10 hover:text-zinc-200',
              )}
            >
              {label}
              <span className="ml-1.5 tabular-nums opacity-70">{n}</span>
            </button>
          )
        })}
      </div>

      <LeadsTable filterStatus={active} />
    </div>
  )
}
