import { useQuery } from '@tanstack/react-query'
import { fetchAgents } from '../api/endpoints'
import { cn } from '../lib/cn'
import { formatTs } from '../lib/format'
import { cardClass } from '../lib/ui'
import { QueryState } from './QueryState'

export function AgentsOverview({ compact = false }: { compact?: boolean }) {
  const query = useQuery({ queryKey: ['agents'], queryFn: fetchAgents })

  return (
    <section className={cardClass}>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">Agentes</h2>
          <p className="text-xs text-zinc-500">Estado, último run y error desde /api/agents</p>
        </div>
        {query.data && <p className="text-[11px] text-zinc-500">{query.data.length}</p>}
      </div>
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="La API no devolvió agentes"
      >
        <div
          className={cn(
            'grid gap-2',
            compact ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3',
          )}
        >
          {(query.data ?? []).map((agent) => (
            <article key={agent.name} className="min-w-0 rounded-xl border border-white/5 bg-surface/60 p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-zinc-100">{agent.name}</p>
                <span className="shrink-0 text-[10px] text-zinc-500">{agent.prompt_version}</span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {agent.last_run_at ? formatTs(agent.last_run_at) : 'Sin última ejecución'}
              </p>
              {!compact && agent.prompt_name && (
                <p className="mt-1 text-xs text-zinc-500">{agent.prompt_name}</p>
              )}
              {agent.last_error ? (
                <p className="mt-2 break-words text-xs text-rose-300">{agent.last_error}</p>
              ) : (
                <p className="mt-2 text-xs text-zinc-500">Sin error reportado</p>
              )}
            </article>
          ))}
        </div>
      </QueryState>
    </section>
  )
}
