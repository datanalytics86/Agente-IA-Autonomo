import { formatTs } from '../lib/format'
import { cn } from '../lib/cn'
import type { LogLevel } from '../lib/types'
import { useAgencyStore } from '../store/useAgencyStore'

const LEVEL: Record<LogLevel, string> = {
  info: 'text-sky-300',
  success: 'text-accent',
  warn: 'text-amber-300',
  error: 'text-rose-400',
}

export function LiveLogs({ limit = 8 }: { limit?: number }) {
  const logs = useAgencyStore((s) => s.logs)

  return (
    <div className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Logs en vivo</h2>
        <p className="text-xs text-zinc-500">Últimos eventos del multiagente</p>
      </div>
      <ul className="space-y-2">
        {logs.slice(0, limit).map((log) => (
          <li
            key={log.id}
            className="rounded-xl border border-white/5 bg-surface/50 px-3 py-2.5"
          >
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
              <span className="font-mono text-zinc-500">{formatTs(log.ts)}</span>
              <span className="font-medium text-zinc-300">{log.agent}</span>
              <span className={cn('uppercase tracking-wide', LEVEL[log.level])}>
                {log.level}
              </span>
            </div>
            <p className="mt-1 text-sm leading-snug text-zinc-200">{log.message}</p>
          </li>
        ))}
        {logs.length === 0 && (
          <li className="py-6 text-center text-sm text-zinc-500">Sin eventos aún</li>
        )}
      </ul>
    </div>
  )
}
