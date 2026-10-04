import { Link, Outlet, createRootRoute, useRouterState } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { AppShell } from '../components/AppShell'
import { AuthGate } from '../components/AuthGate'

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: NotFound,
})

function RootLayout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const isLogin = pathname === '/login'

  return (
    <>
      {isLogin ? (
        <Outlet />
      ) : (
        <AuthGate>
          <AppShell>
            <Outlet />
          </AppShell>
        </AuthGate>
      )}
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          classNames: {
            toast: 'bg-elevated border border-white/10 text-zinc-100',
          },
        }}
      />
    </>
  )
}

function NotFound() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Ruta no encontrada</h1>
      <Link to="/" className="text-sm text-accent">
        Volver al panel
      </Link>
    </div>
  )
}
