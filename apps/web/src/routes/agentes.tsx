import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { toast } from 'sonner'
import { MANUAL_ACTIONS, enqueueAction, fetchAgents, type ManualAction } from '../api/endpoints'
import { errorMessage } from '../api/http'
import { AgentsOverview } from '../components/AgentsOverview'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'
import { LEAD_STATUSES, leadStatusLabel } from '../lib/labels'
import { cardClass, secondaryButtonClass } from '../lib/ui'

const ACTION_LABEL: Record<ManualAction, string> = {
  scout: 'Encolar scout',
  cycle: 'Encolar ciclo',
  followups: 'Encolar seguimientos',
  digest: 'Encolar digest',
}

export const Route = createFileRoute('/agentes')({
  component: AgentesPage,
})

function AgentesPage() {
  const queryClient = useQueryClient()
  const agents = useQuery({ queryKey: ['agents'], queryFn: fetchAgents })
  const [name, setName] = useState<string | null>(null)
  const selected = agents.data?.find((agent) => agent.name === name) ?? agents.data?.[0]
  const action = useMutation({
    mutationFn: enqueueAction,
    onSuccess: async () => {
      toast.success('Job encolado', { description: 'El navegador no envía ni cobra.' })
      await queryClient.invalidateQueries({ queryKey: ['agents'] })
      await queryClient.invalidateQueries({ queryKey: ['events'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Agentes"
        subtitle="El prompt sale de /api/agents. Ejecutar solo encola el job."
      />
      <AgentsOverview />
      <section className={cardClass}>
        <h2 className="text-sm font-semibold text-zinc-100">Ejecutar</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Scout, ciclo, seguimientos o digest. No declara pitches como chequeados.
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {MANUAL_ACTIONS.map((actionName) => (
            <button
              key={actionName}
              type="button"
              className={secondaryButtonClass}
              disabled={action.isPending}
              onClick={() => action.mutate(actionName)}
            >
              {ACTION_LABEL[actionName]}
            </button>
          ))}
        </div>
      </section>
      <section className={cardClass}>
        <h2 className="text-sm font-semibold text-zinc-100">Prompt</h2>
        <QueryState
          isPending={agents.isPending}
          error={agents.error}
          isEmpty={agents.data?.length === 0}
          empty="La API no devolvió agentes"
        >
          {selected && (
            <>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {(agents.data ?? []).map((agent) => (
                  <button
                    key={agent.name}
                    type="button"
                    className={
                      agent.name === selected.name
                        ? 'shrink-0 rounded-full bg-accent/15 px-3 py-1.5 text-xs text-accent ring-1 ring-accent/30'
                        : 'shrink-0 rounded-full bg-surface px-3 py-1.5 text-xs text-zinc-400 ring-1 ring-white/10'
                    }
                    onClick={() => setName(agent.name)}
                  >
                    {agent.name}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-xs text-zinc-500">
                {selected.prompt_name ?? selected.name} · {selected.prompt_version}
              </p>
              <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/5 bg-surface p-4 text-xs leading-relaxed text-zinc-300">
                {selected.prompt_markdown || 'La API no incluyó prompt_markdown para este agente.'}
              </pre>
            </>
          )}
        </QueryState>
      </section>
      <section className={cardClass}>
        <h2 className="text-sm font-semibold text-zinc-100">Estados del motor</h2>
        <ol className="mt-4 flex flex-wrap gap-2">
          {LEAD_STATUSES.map((status, index) => (
            <li
              key={status}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface/70 px-3 py-1.5 text-xs text-zinc-300"
            >
              <span className="font-mono text-accent">{index + 1}</span>
              {leadStatusLabel(status)}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
