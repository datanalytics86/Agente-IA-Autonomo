import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { fetchMe, login } from '../api/endpoints'
import { errorMessage, isUnauthorized } from '../api/http'
import { inputClass, primaryButtonClass } from '../lib/ui'

export const Route = createFileRoute('/login')({
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const me = useQuery({ queryKey: ['auth', 'me'], queryFn: fetchMe })
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useMutation({
    mutationFn: () => login(email.trim(), password),
    onSuccess: async (user) => {
      queryClient.setQueryData(['auth', 'me'], user)
      await navigate({ to: '/' })
    },
  })

  useEffect(() => {
    if (me.data) void navigate({ to: '/' })
  }, [me.data, navigate])

  return (
    <div className="flex min-h-dvh items-center justify-center bg-surface px-4 py-10">
      <form
        className="w-full max-w-sm rounded-2xl border border-white/5 bg-elevated p-5 shadow-card"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <h1 className="text-xl font-semibold tracking-tight text-zinc-50">Ingresar</h1>
        <p className="mt-1 text-sm text-zinc-500">Sesión de administrador. La cookie queda en el navegador.</p>
        <label className="mt-5 block text-xs font-medium text-zinc-400">
          Email
          <input
            className={`${inputClass} mt-1`}
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="mt-3 block text-xs font-medium text-zinc-400">
          Contraseña
          <input
            className={`${inputClass} mt-1`}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {mutation.isError && (
          <p className="mt-3 text-sm text-rose-300" role="alert">
            {errorMessage(mutation.error)}
          </p>
        )}
        {me.isError && !isUnauthorized(me.error) && !mutation.isError && (
          <p className="mt-3 text-sm text-rose-300" role="alert">
            {errorMessage(me.error)}
          </p>
        )}
        <button type="submit" className={`${primaryButtonClass} mt-5 w-full`} disabled={mutation.isPending}>
          {mutation.isPending ? 'Ingresando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
