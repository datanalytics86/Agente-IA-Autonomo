import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { errorMessage } from '../api/http'
import { fetchSettings, putSettings, settingsWithOnline } from '../api/settings'
import type { Settings } from '../api/types'
import { KillSwitchButton } from '../components/KillSwitchButton'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'
import { asRecord } from '../lib/records'
import { cardClass, inputClass, primaryButtonClass } from '../lib/ui'

export const Route = createFileRoute('/config')({
  component: ConfigPage,
})

function ConfigPage() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['settings'], queryFn: fetchSettings })
  const [quotas, setQuotas] = useState('')
  const [prices, setPrices] = useState('')
  const [rates, setRates] = useState('')

  useEffect(() => {
    if (!query.data) return
    setQuotas(JSON.stringify(query.data.quotas ?? {}, null, 2))
    setPrices(JSON.stringify(query.data.prices ?? {}, null, 2))
    setRates(JSON.stringify(query.data.hitl_response_rate_by_channel ?? {}, null, 2))
  }, [query.data])

  const save = useMutation({
    mutationFn: (body: Settings) => putSettings(body),
    onSuccess: async () => {
      toast.success('Ajustes guardados')
      await queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Configuración"
        subtitle="El modo demo o prod se muestra y no se edita. El kill switch sí se guarda."
      />
      <QueryState isPending={query.isPending} error={query.error}>
        {query.data && (
          <>
            <section className={cardClass}>
              <h2 className="text-sm font-semibold text-zinc-100">Modo</h2>
              <label className="mt-3 block text-xs text-zinc-400">
                app_mode
                <input className={`${inputClass} mt-1`} value={query.data.app_mode} disabled readOnly />
              </label>
              <p className="mt-2 text-xs text-zinc-500">Visible y no editable desde esta UI.</p>
            </section>
            <section className={cardClass}>
              <h2 className="text-sm font-semibold text-zinc-100">Kill switch</h2>
              <p className="mt-1 text-xs text-zinc-500">
                Encendido arma los envíos. Apagado los detiene en el motor.
              </p>
              <KillSwitchButton />
            </section>
            <form
              className={`${cardClass} space-y-3`}
              onSubmit={(event) => {
                event.preventDefault()
                if (!query.data) return
                try {
                  const next = settingsWithOnline(query.data, query.data.kill_switch)
                  save.mutate({
                    ...next,
                    quotas: parseObject(quotas, 'Cupos'),
                    prices: parseObject(prices, 'Precios'),
                    hitl_response_rate_by_channel: parseRates(rates),
                    app_mode: query.data.app_mode,
                  })
                } catch (error) {
                  toast.error(errorMessage(error))
                }
              }}
            >
              <h2 className="text-sm font-semibold text-zinc-100">Ajustes</h2>
              <JsonField label="Cupos" value={quotas} onChange={setQuotas} />
              <JsonField label="Precios" value={prices} onChange={setPrices} />
              <JsonField label="Tasas HITL por canal" value={rates} onChange={setRates} />
              <button type="submit" className={primaryButtonClass} disabled={save.isPending}>
                Guardar ajustes
              </button>
            </form>
          </>
        )}
      </QueryState>
    </div>
  )
}

function JsonField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-xs text-zinc-400">
      {label}
      <textarea className={`${inputClass} mt-1 min-h-28 font-mono`} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function parseObject(text: string, label: string): Record<string, unknown> {
  let value: unknown
  try {
    value = JSON.parse(text) as unknown
  } catch {
    throw new Error(`${label} no es JSON válido`)
  }
  const record = asRecord(value)
  if (!record) throw new Error(`${label} debe ser un objeto`)
  return record
}

function parseRates(text: string): Record<string, number> {
  const record = parseObject(text, 'Tasas HITL')
  const out: Record<string, number> = {}
  for (const [key, value] of Object.entries(record)) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      throw new Error(`La tasa de ${key} debe ser un número`)
    }
    out[key] = value
  }
  return out
}
