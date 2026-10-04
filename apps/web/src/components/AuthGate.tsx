import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, type ReactNode } from 'react'
import { fetchMe } from '../api/endpoints'
import { isUnauthorized } from '../api/http'
import { primaryButtonClass } from '../lib/ui'
import { ErrorBanner } from './QueryState'

export function AuthGate({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const me = useQuery({ queryKey: ['auth', 'me'], queryFn: fetchMe })

  useEffect(() => {
    if (me.isError && isUnauthorized(me.error)) {
      void navigate({ to: '/login' })
    }
  }, [me.isError, me.error, navigate])

  if (me.isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-4">
        <p className="text-sm text-zinc-400">Comprobando sesión…</p>
      </div>
    )
  }

  if (me.isError && isUnauthorized(me.error)) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-4">
        <p className="text-sm text-zinc-400">Redirigiendo al login…</p>
      </div>
    )
  }

  if (me.isError) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-4">
        <div className="w-full max-w-md space-y-4">
          <ErrorBanner error={me.error} />
          <button type="button" className={primaryButtonClass} onClick={() => void me.refetch()}>
            Reintentar
          </button>
        </div>
      </div>
    )
  }

  return children
}
