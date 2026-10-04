import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { toast } from 'sonner'
import { fetchMessages, fetchThreads, replyThread } from '../api/endpoints'
import { errorMessage } from '../api/http'
import { cn } from '../lib/cn'
import { inputClass, primaryButtonClass } from '../lib/ui'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'

export const Route = createFileRoute('/conversaciones')({
  component: ConversacionesPage,
})

function ConversacionesPage() {
  const queryClient = useQueryClient()
  const threads = useQuery({ queryKey: ['threads'], queryFn: fetchThreads })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [body, setBody] = useState('')
  const selected = threads.data?.find((thread) => thread.id === selectedId) ?? null
  const messages = useQuery({
    queryKey: ['messages', selected?.lead_id],
    queryFn: () => fetchMessages(selected?.lead_id ?? ''),
    enabled: Boolean(selected?.lead_id),
  })
  const reply = useMutation({
    mutationFn: () => replyThread(selected?.id ?? '', body.trim()),
    onSuccess: async () => {
      toast.success('Respuesta enviada al Checker')
      setBody('')
      await queryClient.invalidateQueries({ queryKey: ['messages'] })
      await queryClient.invalidateQueries({ queryKey: ['threads'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Conversaciones"
        subtitle="La respuesta asistida pasa por el Checker. No sale directo de este navegador."
      />
      <QueryState
        isPending={threads.isPending}
        error={threads.error}
        isEmpty={threads.data?.length === 0}
        empty="No hay hilos"
      >
        <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
          <ul className="space-y-2">
            {(threads.data ?? []).map((thread) => (
              <li key={thread.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(thread.id)}
                  className={cn(
                    'w-full rounded-xl border px-3 py-2 text-left text-sm',
                    thread.id === selectedId
                      ? 'border-accent/30 bg-accent/10 text-accent'
                      : 'border-white/10 bg-elevated text-zinc-200',
                  )}
                >
                  <span className="block font-medium">{thread.lead_id}</span>
                  <span className="mt-1 block break-words text-xs text-zinc-500">
                    {thread.last_message || 'Sin último mensaje'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <section className="min-w-0 rounded-2xl border border-white/5 bg-elevated p-4 shadow-card">
            {!selected && <p className="text-sm text-zinc-500">Elige un hilo.</p>}
            {selected && (
              <>
                <h2 className="text-sm font-semibold text-zinc-100">Lead {selected.lead_id}</h2>
                <QueryState
                  isPending={messages.isPending}
                  error={messages.error}
                  isEmpty={messages.data?.length === 0}
                  empty="Sin mensajes en el hilo"
                >
                  <ul className="mt-3 space-y-2">
                    {(messages.data ?? []).map((message) => (
                      <li key={message.id} className="rounded-xl border border-white/5 bg-surface/60 p-3">
                        <p className="text-[11px] text-zinc-500">
                          {message.direction === 'in' ? 'entrante' : 'saliente'} · {message.channel} ·{' '}
                          {message.status}
                        </p>
                        <p className="mt-1 whitespace-pre-wrap break-words text-sm text-zinc-200">
                          {message.body_text || 'Sin texto'}
                        </p>
                      </li>
                    ))}
                  </ul>
                </QueryState>
                <form
                  className="mt-4 space-y-2"
                  onSubmit={(event) => {
                    event.preventDefault()
                    if (!body.trim() || !selected) return
                    reply.mutate()
                  }}
                >
                  <label className="block text-xs text-zinc-400">
                    Respuesta
                    <textarea
                      className={`${inputClass} mt-1 min-h-24`}
                      value={body}
                      onChange={(event) => setBody(event.target.value)}
                    />
                  </label>
                  <button type="submit" className={primaryButtonClass} disabled={reply.isPending || !body.trim()}>
                    Enviar al Checker
                  </button>
                </form>
              </>
            )}
          </section>
        </div>
      </QueryState>
    </div>
  )
}
