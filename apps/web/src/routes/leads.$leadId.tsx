import { useQuery } from '@tanstack/react-query'
import { Link, createFileRoute } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { fetchLead } from '../api/endpoints'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'
import { formatClp, formatTs } from '../lib/format'
import { leadStatusLabel } from '../lib/labels'
import { asRecord, field } from '../lib/records'
import { cardClass } from '../lib/ui'

export const Route = createFileRoute('/leads/$leadId')({
  component: LeadDetailPage,
})

function LeadDetailPage() {
  const { leadId } = Route.useParams()
  const query = useQuery({
    queryKey: ['leads', leadId],
    queryFn: () => fetchLead(leadId),
  })
  const lead = query.data

  return (
    <div className="space-y-5">
      <PageHeader
        title={lead?.business ?? 'Lead'}
        subtitle="Detalle, timeline, mensajes, artefactos y auditoría. Nada de esto se suma como ingreso."
      />
      <Link to="/leads" className="text-sm text-accent">
        Volver al listado
      </Link>
      <QueryState isPending={query.isPending} error={query.error}>
        {lead && (
          <div className="space-y-4">
            <section className={cardClass}>
              <h2 className="text-sm font-semibold text-zinc-100">Datos</h2>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Item k="Estado" v={leadStatusLabel(lead.status)} />
                <Item k="Origen" v={lead.source} />
                <Item k="Rubro" v={lead.category} />
                <Item k="Comuna" v={lead.city ? `${lead.commune}, ${lead.city}` : lead.commune} />
                <Item
                  k="Valor estimado"
                  v={
                    typeof lead.estimated_value_clp === 'number'
                      ? formatClp(lead.estimated_value_clp)
                      : '—'
                  }
                />
                <Item k="Pausa desde" v={lead.paused_from ? leadStatusLabel(lead.paused_from) : '—'} />
                <Item k="High value" v={lead.high_value ? 'sí' : 'no'} />
                <Item
                  k="Score"
                  v={typeof lead.opportunity_score === 'number' ? String(lead.opportunity_score) : '—'}
                />
              </dl>
            </section>
            <Section title="Diagnóstico">
              <Pretty value={lead.diagnosis} empty="La API no incluyó diagnóstico" />
            </Section>
            <Section title="Timeline">
              <EventList value={lead.timeline} empty="La API no incluyó timeline" />
            </Section>
            <Section title="Mensajes">
              {lead.messages === undefined ? (
                <p className="text-sm text-zinc-500">La API no incluyó mensajes</p>
              ) : lead.messages.length === 0 ? (
                <p className="text-sm text-zinc-500">Sin mensajes</p>
              ) : (
                <ul className="space-y-2">
                  {lead.messages.map((message) => (
                    <li key={message.id} className="rounded-xl border border-white/5 bg-surface/60 p-3">
                      <p className="text-[11px] text-zinc-500">
                        {message.direction} · {message.channel} · {message.status}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap break-words text-sm text-zinc-200">
                        {message.body_text || 'Sin texto'}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Artefactos">
              <EventList value={lead.artifacts} empty="La API no incluyó artefactos" kind="artifact" />
            </Section>
            <Section title="Auditoría web">
              <Pretty value={lead.website_audit} empty="Sin auditoría web" />
            </Section>
          </div>
        )}
      </QueryState>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={cardClass}>
      <h2 className="mb-3 text-sm font-semibold text-zinc-100">{title}</h2>
      {children}
    </section>
  )
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-xl border border-white/5 bg-surface/60 p-3">
      <dt className="text-[11px] uppercase tracking-wide text-zinc-500">{k}</dt>
      <dd className="mt-1 break-words text-sm text-zinc-200">{v}</dd>
    </div>
  )
}

function Pretty({ value, empty }: { value: unknown; empty: string }) {
  if (value == null) return <p className="text-sm text-zinc-500">{empty}</p>
  if (typeof value === 'string') return <p className="whitespace-pre-wrap text-sm text-zinc-200">{value}</p>
  const record = asRecord(value)
  if (!record || Object.keys(record).length === 0) {
    return <p className="text-sm text-zinc-500">{empty}</p>
  }
  const summary = field(record, 'summary') ?? field(record, 'text') ?? field(record, 'diagnosis')
  if (summary && Object.keys(record).length <= 3) {
    return <p className="whitespace-pre-wrap text-sm text-zinc-200">{summary}</p>
  }
  return (
    <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/5 bg-surface p-3 text-xs text-zinc-300">
      {JSON.stringify(record, null, 2)}
    </pre>
  )
}

function EventList({
  value,
  empty,
  kind = 'event',
}: {
  value: unknown
  empty: string
  kind?: 'event' | 'artifact'
}) {
  if (!Array.isArray(value)) return <p className="text-sm text-zinc-500">{empty}</p>
  if (value.length === 0) return <p className="text-sm text-zinc-500">Sin registros</p>
  return (
    <ul className="space-y-2">
      {value.map((item, index) => {
        const record = asRecord(item)
        const title =
          kind === 'artifact'
            ? [field(record, 'kind') ?? 'artefacto', field(record, 'version')].filter(Boolean).join(' ')
            : [field(record, 'from_status'), field(record, 'to_status')].filter(Boolean).join(' → ') ||
              `Evento ${index + 1}`
        const ts = field(record, 'ts')
        const detail =
          kind === 'artifact'
            ? (field(record, 'path') ?? JSON.stringify(item))
            : [ts ? formatTs(ts) : null, field(record, 'actor'), field(record, 'reason')]
                .filter(Boolean)
                .join(' · ') || JSON.stringify(item)
        return (
          <li key={field(record, 'id') ?? String(index)} className="rounded-xl border border-white/5 bg-surface/60 p-3">
            <p className="text-sm text-zinc-100">{title}</p>
            <p className="mt-1 break-words text-xs text-zinc-400">{detail}</p>
          </li>
        )
      })}
    </ul>
  )
}
