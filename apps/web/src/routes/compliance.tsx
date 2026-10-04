import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { toast } from 'sonner'
import {
  addSuppression,
  deleteSuppression,
  fetchDataRequests,
  fetchSuppression,
  patchDataRequest,
} from '../api/endpoints'
import { errorMessage } from '../api/http'
import type { DataRequestEntry } from '../api/types'
import { formatTs } from '../lib/format'
import { cardClass, ghostButtonClass, inputClass, primaryButtonClass } from '../lib/ui'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'

const KINDS = ['email', 'domain', 'instagram', 'linkedin', 'phone']
const REQUEST_STATUSES = ['open', 'done', 'rejected']

export const Route = createFileRoute('/compliance')({
  component: CompliancePage,
})

function CompliancePage() {
  return (
    <div className="space-y-5">
      <PageHeader
        title="Compliance"
        subtitle="Supresión por hash y solicitudes de derechos. La lista no muestra el valor en claro."
      />
      <SuppressionSection />
      <RightsSection />
    </div>
  )
}

function SuppressionSection() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['suppression'], queryFn: fetchSuppression })
  const [kind, setKind] = useState('email')
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  const add = useMutation({
    mutationFn: () => addSuppression({ kind, value: value.trim(), reason: reason.trim() }),
    onSuccess: async () => {
      setValue('')
      setReason('')
      toast.success('Supresión agregada')
      await queryClient.invalidateQueries({ queryKey: ['suppression'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const remove = useMutation({
    mutationFn: deleteSuppression,
    onSuccess: async () => {
      toast.success('Supresión borrada')
      await queryClient.invalidateQueries({ queryKey: ['suppression'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-zinc-100">Supresión</h2>
      <form
        className={`${cardClass} grid gap-2`}
        onSubmit={(event) => {
          event.preventDefault()
          if (!value.trim() || !reason.trim()) return
          add.mutate()
        }}
      >
        <select className={inputClass} value={kind} aria-label="Tipo" onChange={(event) => setKind(event.target.value)}>
          {KINDS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <input
          className={inputClass}
          value={value}
          placeholder="Valor a suprimir"
          aria-label="Valor"
          onChange={(event) => setValue(event.target.value)}
        />
        <input
          className={inputClass}
          value={reason}
          placeholder="Motivo"
          aria-label="Motivo"
          onChange={(event) => setReason(event.target.value)}
        />
        <button type="submit" className={primaryButtonClass} disabled={add.isPending}>
          Agregar
        </button>
      </form>
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="No hay supresiones"
      >
        <ul className="space-y-2">
          {(query.data ?? []).map((row) => (
            <li key={row.id} className="rounded-2xl border border-white/5 bg-elevated p-4">
              <p className="text-sm text-zinc-100">
                {row.kind} · <span className="font-mono text-xs text-zinc-400">{row.value_hash}</span>
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {row.reason || 'Sin motivo'}
                {row.created_at ? ` · ${formatTs(row.created_at)}` : ''}
              </p>
              <button
                type="button"
                className={`${ghostButtonClass} mt-3`}
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm('¿Borrar esta supresión?')) remove.mutate(row.id)
                }}
              >
                Borrar
              </button>
            </li>
          ))}
        </ul>
      </QueryState>
    </section>
  )
}

function RightsSection() {
  const query = useQuery({ queryKey: ['data-requests'], queryFn: fetchDataRequests })

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-zinc-100">Derechos</h2>
      <QueryState
        isPending={query.isPending}
        error={query.error}
        isEmpty={query.data?.length === 0}
        empty="No hay solicitudes"
      >
        <ul className="space-y-2">
          {(query.data ?? []).map((row) => (
            <RequestRow key={row.id} row={row} />
          ))}
        </ul>
      </QueryState>
    </section>
  )
}

function RequestRow({ row }: { row: DataRequestEntry }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState(row.status)
  const due = row.due_at ? new Date(row.due_at) : null
  const overdue = due ? due.getTime() < Date.now() && row.status === 'open' : false
  const options = REQUEST_STATUSES.includes(row.status) ? REQUEST_STATUSES : [row.status, ...REQUEST_STATUSES]
  const update = useMutation({
    mutationFn: () => patchDataRequest(row.id, status),
    onSuccess: async () => {
      toast.success('Solicitud actualizada')
      await queryClient.invalidateQueries({ queryKey: ['data-requests'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <li className="rounded-2xl border border-white/5 bg-elevated p-4">
      <p className="text-sm font-medium text-zinc-100">
        {row.kind} · {row.status}
      </p>
      <p className="mt-1 break-words text-xs text-zinc-500">
        {row.requester_email || 'Sin email'}
        {row.due_at ? ` · vence ${formatTs(row.due_at)}` : ''}
      </p>
      {overdue && <p className="mt-1 text-xs text-amber-300">Vencida</p>}
      {row.details && <p className="mt-2 break-words text-sm text-zinc-300">{row.details}</p>}
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <select className={inputClass} value={status} aria-label="Estado" onChange={(event) => setStatus(event.target.value)}>
          {options.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <button type="button" className={primaryButtonClass} disabled={update.isPending} onClick={() => update.mutate()}>
          Actualizar
        </button>
      </div>
    </li>
  )
}
