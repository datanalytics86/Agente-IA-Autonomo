import type { ReactNode } from 'react'
import { errorMessage } from '../api/http'

export function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100"
    >
      <p className="font-medium">No se pudieron cargar los datos</p>
      <p className="mt-1 text-rose-100/80">{errorMessage(error)}</p>
    </div>
  )
}

export function QueryState({
  isPending,
  error,
  isEmpty = false,
  empty = 'Sin datos',
  children,
}: {
  isPending: boolean
  error: unknown
  isEmpty?: boolean
  empty?: string
  children: ReactNode
}) {
  if (isPending) return <p className="text-sm text-zinc-500">Cargando…</p>
  if (error) return <ErrorBanner error={error} />
  if (isEmpty) {
    return (
      <p className="rounded-2xl border border-dashed border-white/10 py-10 text-center text-sm text-zinc-500">
        {empty}
      </p>
    )
  }
  return children
}
