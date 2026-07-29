import { Link, useRouterState } from '@tanstack/react-router'
import {
  Activity,
  Bot,
  LayoutDashboard,
  Menu,
  Settings,
  Users,
  X,
  Power,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useAgencyStore } from '../store/useAgencyStore'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/', label: 'Panel', icon: LayoutDashboard },
  { to: '/agentes', label: 'Agentes', icon: Bot },
  { to: '/leads', label: 'Leads', icon: Users },
  { to: '/logs', label: 'Logs', icon: Activity },
  { to: '/config', label: 'Config', icon: Settings },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const systemOnline = useAgencyStore((s) => s.systemOnline)
  const toggleSystem = useAgencyStore((s) => s.toggleSystem)

  return (
    <div className="min-h-dvh bg-surface text-zinc-100">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-white/5 bg-surface/95 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Abrir menú"
            className="rounded-lg border border-white/10 p-2 text-zinc-300 hover:bg-white/5"
            onClick={() => setOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div>
            <p className="text-sm font-semibold tracking-tight">Agente IA Autónomo</p>
            <p className="text-[11px] text-zinc-500">Landings · pymes Chile</p>
          </div>
        </div>
        <StatusPill online={systemOnline} onClick={toggleSystem} />
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Cerrar menú"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-white/10 bg-elevated p-4 shadow-2xl">
            <div className="mb-6 flex items-center justify-between">
              <Brand />
              <button
                type="button"
                className="rounded-lg p-2 text-zinc-400 hover:bg-white/5"
                onClick={() => setOpen(false)}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <NavList pathname={pathname} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="mx-auto flex w-full max-w-[1400px]">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-white/5 bg-elevated/40 px-4 py-6 lg:flex">
          <Brand />
          <div className="mt-8 flex-1">
            <NavList pathname={pathname} />
          </div>
          <button
            type="button"
            onClick={toggleSystem}
            className={cn(
              'mt-4 flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition',
              systemOnline
                ? 'border-accent/30 bg-accent/10 text-accent hover:bg-accent/15'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/15',
            )}
          >
            <Power className="h-4 w-4" />
            {systemOnline ? 'Sistema online' : 'Sistema offline'}
          </button>
        </aside>

        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  )
}

function Brand() {
  return (
    <div className="px-1">
      <div className="flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 ring-1 ring-accent/30">
          <Bot className="h-5 w-5 text-accent" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">Agente IA</p>
          <p className="text-[11px] text-zinc-500">Autónomo · CL</p>
        </div>
      </div>
    </div>
  )
}

function NavList({
  pathname,
  onNavigate,
}: {
  pathname: string
  onNavigate?: () => void
}) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon }) => {
        const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
        return (
          <Link
            key={to}
            to={to}
            onClick={onNavigate}
            className={cn(
              'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
              active
                ? 'bg-accent/15 text-accent ring-1 ring-accent/25'
                : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-100',
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        )
      })}
    </nav>
  )
}

function StatusPill({ online, onClick }: { online: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1',
        online
          ? 'bg-accent/10 text-accent ring-accent/25'
          : 'bg-amber-500/10 text-amber-300 ring-amber-500/25',
      )}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          online ? 'bg-accent' : 'bg-amber-400',
        )}
      />
      {online ? 'Online' : 'Offline'}
    </button>
  )
}
