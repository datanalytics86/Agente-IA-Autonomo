import { createFileRoute } from '@tanstack/react-router'
import { AgentsOverview } from '../components/AgentsOverview'
import { ORCHESTRATOR_PROMPT } from '../lib/mock'
import { STATUS_FLOW, STATUS_LABELS } from '../lib/types'

export const Route = createFileRoute('/agentes')({
  component: AgentesPage,
})

function AgentesPage() {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Agentes</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Stack completo y flujo de negocio alineado con el motor Python
        </p>
      </header>

      <AgentsOverview />

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold text-zinc-100">Flujo del pipeline</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Scout → Diagnoser → Builder → Filmer → Checker → Pitcher → Mobile
        </p>
        <ol className="mt-4 flex flex-wrap gap-2">
          {STATUS_FLOW.map((s, i) => (
            <li
              key={s}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface/70 px-3 py-1.5 text-xs text-zinc-300"
            >
              <span className="font-mono text-accent">{i + 1}</span>
              {STATUS_LABELS[s]}
            </li>
          ))}
          <li className="inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-200">
            + Revisión HITL
          </li>
        </ol>
      </section>

      <section className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
        <h2 className="text-sm font-semibold text-zinc-100">Prompt del Orchestrator</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Misma semántica que <code className="text-accent">engine/prompts/orchestrator.md</code>
        </p>
        <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-white/5 bg-surface p-4 text-xs leading-relaxed text-zinc-300">
          {ORCHESTRATOR_PROMPT}
        </pre>
      </section>
    </div>
  )
}
