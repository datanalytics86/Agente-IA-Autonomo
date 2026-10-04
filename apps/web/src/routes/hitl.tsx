import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { toast } from 'sonner'
import { approveHitl, editHitl, fetchApprovals, rejectHitl } from '../api/endpoints'
import { errorMessage } from '../api/http'
import type { Approval } from '../api/types'
import { approvalDiff, approvalDraft } from '../lib/records'
import { ghostButtonClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../lib/ui'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'

export const Route = createFileRoute('/hitl')({
  component: HitlPage,
})

function HitlPage() {
  const query = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () => fetchApprovals('pending'),
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Bandeja HITL"
        subtitle="Aprobar llama a la API. El lead vuelve a la etapa en pausa y no queda enviado en el cliente."
      />
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="No hay aprobaciones pendientes"
      >
        <div className="space-y-3">
          {(query.data ?? []).map((approval) => (
            <ApprovalCard key={approval.id} approval={approval} />
          ))}
        </div>
      </QueryState>
    </div>
  )
}

function ApprovalCard({ approval }: { approval: Approval }) {
  const queryClient = useQueryClient()
  const draft = approvalDraft(approval.payload)
  const diff = approvalDiff(approval.payload)
  const [subject, setSubject] = useState(draft.subject)
  const [body, setBody] = useState(draft.body_text)
  const [note, setNote] = useState('')

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['approvals'] })
    await queryClient.invalidateQueries({ queryKey: ['leads'] })
  }

  const edit = useMutation({
    mutationFn: () => editHitl(approval.id, { subject, body_text: body }),
    onSuccess: async () => {
      toast.success('Edición enviada al Checker')
      await invalidate()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const approve = useMutation({
    mutationFn: () => approveHitl(approval.id),
    onSuccess: async () => {
      toast.success('Aprobación enviada', {
        description: 'El motor retoma la etapa en pausa. Este cliente no marca el lead como enviado.',
      })
      await invalidate()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const reject = useMutation({
    mutationFn: () => rejectHitl(approval.id, note),
    onSuccess: async () => {
      toast.message('Rechazo enviado')
      await invalidate()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const busy = edit.isPending || approve.isPending || reject.isPending

  return (
    <article className="rounded-2xl border border-white/5 bg-elevated p-4 shadow-card sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-zinc-100">{approval.kind}</h2>
          <p className="mt-1 text-xs text-zinc-500">
            {approval.status} · lead {approval.lead_id}
          </p>
        </div>
        <Link
          to="/leads/$leadId"
          params={{ leadId: approval.lead_id }}
          className="text-xs text-accent"
        >
          Ver lead
        </Link>
      </div>
      {diff && (
        <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/5 bg-surface p-3 text-xs text-zinc-300">
          {diff}
        </pre>
      )}
      <label className="mt-3 block text-xs text-zinc-400">
        Asunto
        <input className={`${inputClass} mt-1`} value={subject} onChange={(event) => setSubject(event.target.value)} />
      </label>
      <label className="mt-3 block text-xs text-zinc-400">
        Mensaje
        <textarea
          className={`${inputClass} mt-1 min-h-28`}
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
      </label>
      <p className="mt-2 text-[11px] text-zinc-500">
        Aprobar no envía el texto del cuadro. Si lo cambias, guarda la edición primero.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => edit.mutate()}>
          Guardar edición
        </button>
        <button type="button" className={primaryButtonClass} disabled={busy} onClick={() => approve.mutate()}>
          Aprobar
        </button>
      </div>
      <label className="mt-3 block text-xs text-zinc-400">
        Nota de rechazo
        <input className={`${inputClass} mt-1`} value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <button type="button" className={`${ghostButtonClass} mt-2`} disabled={busy} onClick={() => reject.mutate()}>
        Rechazar
      </button>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-zinc-500">Contexto</summary>
        <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/5 bg-surface p-3 text-xs text-zinc-300">
          {JSON.stringify(approval.payload ?? {}, null, 2)}
        </pre>
      </details>
    </article>
  )
}
