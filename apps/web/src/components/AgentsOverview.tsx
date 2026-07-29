import { cn } from '../lib/cn'
import type { AgentRuntimeStatus } from '../lib/types'
import { useAgencyStore } from '../store/useAgencyStore'

const STATUS_STYLES: Record<
  AgentRuntimeStatus,
  { label: string; dot: string; chip: string }
> = {
  idle: {
    label: 'Idle',
    dot: 'bg-zinc-400',
    chip: 'bg-zinc-500/10 text-zinc-300 ring-zinc-500/20',
  },
  running: {
    label: 'Running',
    dot: 'bg-accent animate-pulse',
    chip: 'bg-accent/10 text-accent ring-accent/25',
  },
  waiting: {
    label: 'Waiting',
    dot: 'bg-amber-400',
    chip: 'bg-amber-500/10 text-amber-300 ring-amber-500/25',
  },
  offline: {
    label: 'Offline',
    dot: 'bg-zinc-600',
    chip: 'bg-zinc-800 text-zinc-500 ring-white/5',
  },
}

export function AgentsOverview({ compact = false }: { compact?: boolean }) {
  const agents = useAgencyStore((s) => s.agents)

  return (
    <div className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">Agentes</h2>
          <p className="text-xs text-zinc-500">Orchestrator + 7 especialistas</p>
        </div>
        <p className="text-[11px] text-zinc-500">{agents.length} activos en stack</p>
      </div>
      <div
        className={cn(
          'grid gap-2',
          compact ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-4',
        )}
      >
        {agents.map((a) => {
          const st = STATUS_STYLES[a.status]
          return (
            <div
              key={a.name}
              className="rounded-xl border border-white/5 bg-surface/60 p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-zinc-100">{a.name}</p>
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1',
                    st.chip,
                  )}
                >
                  <span className={cn('h-1.5 w-1.5 rounded-full', st.dot)} />
                  {st.label}
                </span>
              </div>
              {!compact && (
                <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{a.role}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
