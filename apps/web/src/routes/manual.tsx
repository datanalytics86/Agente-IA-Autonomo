import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { toast } from 'sonner'
import { fetchManualQueue, markManualSent } from '../api/endpoints'
import { errorMessage } from '../api/http'
import type { Message } from '../api/types'
import { manualProfileUrl } from '../lib/records'
import { ghostButtonClass, primaryButtonClass, secondaryButtonClass } from '../lib/ui'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'

export const Route = createFileRoute('/manual')({
  component: ManualPage,
})

function ManualPage() {
  const query = useQuery({ queryKey: ['manual-queue'], queryFn: fetchManualQueue })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Bandeja manual"
        subtitle="Instagram y LinkedIn se copian y se marcan enviados a mano. El navegador no los manda."
      />
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="No hay borradores en la cola manual"
      >
        <div className="space-y-3">
          {(query.data ?? []).map((message) => (
            <ManualCard key={message.id} message={message} />
          ))}
        </div>
      </QueryState>
    </div>
  )
}

function ManualCard({ message }: { message: Message }) {
  const queryClient = useQueryClient()
  const profile = manualProfileUrl(message)
  const mark = useMutation({
    mutationFn: () => markManualSent(message.id),
    onSuccess: async () => {
      toast.success('Marcado como enviado en la cola manual')
      await queryClient.invalidateQueries({ queryKey: ['manual-queue'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <article className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <p className="text-sm font-semibold text-zinc-100">
        {message.channel} · {message.status}
      </p>
      <p className="mt-1 text-xs text-zinc-500">
        {message.direction}
        {message.lead_id ? ` · lead ${message.lead_id}` : ''}
      </p>
      {message.subject && <p className="mt-3 text-sm text-zinc-200">{message.subject}</p>}
      <p className="mt-3 whitespace-pre-wrap break-words text-sm text-zinc-300">
        {message.body_text || 'Sin texto'}
      </p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button
          type="button"
          className={secondaryButtonClass}
          onClick={() => {
            const text = message.body_text ?? ''
            if (!text) {
              toast.error('El mensaje no trae texto')
              return
            }
            void navigator.clipboard.writeText(text).then(
              () => toast.success('Texto copiado'),
              () => toast.error('No se pudo copiar'),
            )
          }}
        >
          Copiar
        </button>
        {profile ? (
          <a href={profile} target="_blank" rel="noreferrer" className={secondaryButtonClass}>
            Abrir perfil
          </a>
        ) : (
          <button type="button" className={ghostButtonClass} disabled>
            Sin perfil en la API
          </button>
        )}
        <button
          type="button"
          className={primaryButtonClass}
          disabled={mark.isPending}
          onClick={() => mark.mutate()}
        >
          Marcar enviado
        </button>
      </div>
    </article>
  )
}
