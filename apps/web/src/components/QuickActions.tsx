import { Radar, Send, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { useAgencyStore } from '../store/useAgencyStore'
import { Link } from '@tanstack/react-router'

export function QuickActions() {
  const runScout = useAgencyStore((s) => s.runScout)
  const runPitchBatch = useAgencyStore((s) => s.runPitchBatch)
  const online = useAgencyStore((s) => s.systemOnline)
  const revisionCount = useAgencyStore(
    (s) => s.leads.filter((l) => l.status === 'revision').length,
  )

  return (
    <div className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Acciones rápidas</h2>
        <p className="text-xs text-zinc-500">Simulan el motor demo en el store</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button
          type="button"
          disabled={!online}
          onClick={() => {
            runScout()
            toast.success('Scout ejecutado', {
              description: 'Se agregaron leads chilenos al pipeline',
            })
          }}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-surface transition hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Radar className="h-4 w-4" />
          Correr Scout
        </button>
        <button
          type="button"
          disabled={!online}
          onClick={() => {
            const before = useAgencyStore.getState().leads.filter((l) => l.status === 'pitch_listo').length
            runPitchBatch()
            if (before === 0) {
              toast.message('Sin pitches listos', {
                description: 'Avanza leads hasta pitch_listo primero',
              })
            } else {
              toast.success('Batch de pitches enviado', {
                description: `${before} lead(s) → enviado (simulado)`,
              })
            }
          }}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
          Enviar pitches
        </button>
        <Link
          to="/leads"
          search={{ status: 'revision' }}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:bg-amber-500/15"
        >
          <ShieldCheck className="h-4 w-4" />
          Revisar deals
          {revisionCount > 0 && (
            <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
              {revisionCount}
            </span>
          )}
        </Link>
      </div>
    </div>
  )
}
