import { useQuery } from '@tanstack/react-query'
import { Outlet, createFileRoute, useRouterState } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { fetchLeads } from '../api/endpoints'
import { LeadsTable } from '../components/LeadsTable'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'
import { cn } from '../lib/cn'
import { LEAD_STATUSES, leadStatusLabel } from '../lib/labels'
import { inputClass, secondaryButtonClass } from '../lib/ui'

type LeadSearch = {
  status?: string
  q?: string
  page?: number
}

export const Route = createFileRoute('/leads')({
  validateSearch: (search: Record<string, unknown>): LeadSearch => {
    const status = typeof search.status === 'string' && search.status !== 'all' ? search.status : undefined
    const q = typeof search.q === 'string' && search.q.trim() ? search.q : undefined
    const pageRaw = search.page
    const pageNumber =
      typeof pageRaw === 'number' ? pageRaw : typeof pageRaw === 'string' ? Number(pageRaw) : undefined
    return {
      status,
      q,
      page: pageNumber && Number.isFinite(pageNumber) && pageNumber > 0 ? pageNumber : undefined,
    }
  },
  component: LeadsPage,
})

function LeadsPage() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  if (pathname !== '/leads' && pathname !== '/leads/') return <Outlet />
  return <LeadsList />
}

function LeadsList() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const page = search.page ?? 1
  const [draftQ, setDraftQ] = useState(search.q ?? '')
  const query = useQuery({
    queryKey: ['leads', { status: search.status, q: search.q, page }],
    queryFn: () =>
      fetchLeads({
        status: search.status,
        q: search.q,
        page,
        page_size: 20,
      }),
  })

  useEffect(() => {
    setDraftQ(search.q ?? '')
  }, [search.q])

  return (
    <div className="space-y-5">
      <PageHeader
        title="Leads"
        subtitle={
          query.data
            ? `${query.data.total} en total · página ${query.data.page}. El valor estimado no es ingreso.`
            : 'Listado paginado. El valor estimado no es ingreso.'
        }
      />
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          void navigate({ search: { status: search.status, q: draftQ.trim() || undefined, page: 1 } })
        }}
      >
        <input
          className={inputClass}
          value={draftQ}
          placeholder="Buscar negocio"
          aria-label="Buscar leads"
          onChange={(event) => setDraftQ(event.target.value)}
        />
        <button type="submit" className={secondaryButtonClass}>
          Buscar
        </button>
      </form>
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        <StatusChip
          label="Todos"
          active={!search.status}
          onClick={() => void navigate({ search: { q: search.q, page: 1 } })}
        />
        {LEAD_STATUSES.map((status) => (
          <StatusChip
            key={status}
            label={leadStatusLabel(status)}
            active={search.status === status}
            onClick={() => void navigate({ search: { status, q: search.q, page: 1 } })}
          />
        ))}
      </div>
      <QueryState isPending={query.isPending} error={query.error}>
        <LeadsTable items={query.data?.items ?? []} />
      </QueryState>
      {query.data && (
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={page <= 1}
            onClick={() => void navigate({ search: { ...search, page: page - 1 } })}
          >
            Anterior
          </button>
          <p className="text-xs text-zinc-500">
            {query.data.page_size} por página
          </p>
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={page * query.data.page_size >= query.data.total}
            onClick={() => void navigate({ search: { ...search, page: page + 1 } })}
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  )
}

function StatusChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition',
        active
          ? 'bg-accent/15 text-accent ring-accent/30'
          : 'bg-elevated text-zinc-400 ring-white/10 hover:text-zinc-200',
      )}
    >
      {label}
    </button>
  )
}
