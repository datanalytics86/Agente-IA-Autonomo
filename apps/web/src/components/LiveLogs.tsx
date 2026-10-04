import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { fetchEvents } from '../api/endpoints'
import { cn } from '../lib/cn'
import { formatTs } from '../lib/format'
import { cardClass, inputClass } from '../lib/ui'
import { QueryState } from './QueryState'

const LEVEL: Record<string, string> = {
  info: 'text-sky-300',
  success: 'text-accent',
  warn: 'text-amber-300',
  error: 'text-rose-400',
  debug: 'text-zinc-500',
}

export function LiveLogs({
  limit = 8,
  showFilters = false,
}: {
  limit?: number
  showFilters?: boolean
}) {
  const queryClient = useQueryClient()
  const [level, setLevel] = useState('')
  const [agent, setAgent] = useState('')
  const query = useQuery({
    queryKey: ['events', { limit, level, agent }],
    queryFn: () =>
      fetchEvents({
        limit,
        level: level || undefined,
        agent: agent || undefined,
      }),
    refetchInterval: 20_000,
  })

  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    const source = new EventSource('/api/events/stream', { withCredentials: true })
    source.onmessage = () => {
      void queryClient.invalidateQueries({ queryKey: ['events'] })
    }
    source.onerror = () => {
      source.close()
    }
    return () => source.close()
  }, [queryClient])

  return (
    <section className={cardClass}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Eventos</h2>
        <p className="text-xs text-zinc-500">
          {query.data ? `${query.data.length} en esta consulta` : 'GET /api/events'}
        </p>
      </div>
      {showFilters && (
        <div className="mb-4 grid gap-2 sm:grid-cols-2">
          <select
            className={inputClass}
            value={level}
            aria-label="Filtrar por nivel"
            onChange={(event) => setLevel(event.target.value)}
          >
            <option value="">Todos los niveles</option>
            <option value="debug">debug</option>
            <option value="info">info</option>
            <option value="warn">warn</option>
            <option value="error">error</option>
          </select>
          <input
            className={inputClass}
            value={agent}
            placeholder="Agente"
            aria-label="Filtrar por agente"
            onChange={(event) => setAgent(event.target.value)}
          />
        </div>
      )}
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="No hay eventos"
      >
        <ul className="space-y-2">
          {(query.data ?? []).map((log) => (
            <li key={log.id} className="rounded-xl border border-white/5 bg-surface/50 px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
                <span className="font-mono text-zinc-500">{formatTs(log.ts)}</span>
                <span className="font-medium text-zinc-300">{log.agent}</span>
                <span className={cn('uppercase tracking-wide', LEVEL[log.level] ?? 'text-zinc-400')}>
                  {log.level}
                </span>
              </div>
              <p className="mt-1 break-words text-sm leading-snug text-zinc-200">{log.message}</p>
            </li>
          ))}
        </ul>
      </QueryState>
    </section>
  )
}
