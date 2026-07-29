import { Outlet, createRootRoute } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { AppShell } from '../components/AppShell'

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <AppShell>
      <Outlet />
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          classNames: {
            toast: 'bg-elevated border border-white/10 text-zinc-100',
          },
        }}
      />
    </AppShell>
  )
}
