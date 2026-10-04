import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import {
  Activity,
  Bot,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  MessagesSquare,
  Scale,
  Settings,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { logout } from '../api/endpoints'
import { errorMessage } from '../api/http'
import { fetchSettings, SENDS_STOPPED_LABEL, sendsStopped } from '../api/settings'
import { cn } from '../lib/cn'
import { useUiStore } from '../store/useUiStore'
import { KillSwitchButton } from './KillSwitchButton'

const NAV = [
  { to: '/', label: 'Panel', icon: LayoutDashboard },
  { to: '/hitl', label: 'Bandeja HITL', icon: ShieldCheck },
  { to: '/manual', label: 'Bandeja manual', icon: Inbox },
  { to: '/conversaciones', label: 'Conversaciones', icon: MessagesSquare },
  { to: '/leads', label: 'Leads', icon: Users },
  { to: '/proyectos', label: 'Proyectos', icon: FolderKanban },
  { to: '/agentes', label: 'Agentes', icon: Bot },
  { to: '/logs', label: 'Logs', icon: Activity },
  { to: '/compliance', label: 'Compliance', icon: Scale },
  { to: '/config', label: 'Config', icon: Settings },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  const open = useUiStore((s) => s.sidebarOpen)
  const setOpen = useUiStore((s) => s.setSidebarOpen)
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const settings = useQuery({ queryKey: ['settings'], queryFn: fetchSettings })
  const stopped = settings.data ? sendsStopped(settings.data) : false

  return (
    <div className="min-h-dvh bg-surface text-zinc-100">
      <header className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-white/5 bg-surface/95 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            aria-label="Abrir menú"
            className="rounded-lg border border-white/10 p-2 text-zinc-300 hover:bg-white/5"
            onClick={() => setOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">Agente IA Autónomo</p>
            <p className="text-[11px] text-zinc-500">
              {settings.data ? `modo ${settings.data.app_mode}` : 'Landings · pymes Chile'}
            </p>
          </div>
        </div>
        <KillSwitchButton variant="pill" />
      </header>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/60"
            aria-label="Cerrar menú"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-72 max-w-[85vw] flex-col border-r border-white/10 bg-elevated p-4 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <Brand mode={settings.data?.app_mode} />
              <button
                type="button"
                className="rounded-lg p-2 text-zinc-400 hover:bg-white/5"
                aria-label="Cerrar"
                onClick={() => setOpen(false)}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <NavList pathname={pathname} onNavigate={() => setOpen(false)} />
            </div>
            <KillSwitchButton />
            <LogoutButton />
          </aside>
        </div>
      )}

      <div className="mx-auto flex w-full max-w-[1400px]">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-white/5 bg-elevated/40 px-4 py-6 lg:flex">
          <Brand mode={settings.data?.app_mode} />
          <div className="mt-6 min-h-0 flex-1 overflow-y-auto">
            <NavList pathname={pathname} />
          </div>
          <KillSwitchButton />
          <LogoutButton />
        </aside>

        <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          {stopped && (
            <p className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
              {SENDS_STOPPED_LABEL}
            </p>
          )}
          {settings.isError && (
            <p className="mb-4 text-sm text-rose-300">No se pudo leer el kill switch.</p>
          )}
          {children}
        </main>
      </div>
    </div>
  )
}

function Brand({ mode }: { mode?: string }) {
  return (
    <div className="px-1">
      <div className="flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 ring-1 ring-accent/30">
          <Bot className="h-5 w-5 text-accent" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">Agente IA</p>
          <p className="text-[11px] text-zinc-500">{mode ? `modo ${mode}` : 'Autónomo · CL'}</p>
        </div>
      </div>
    </div>
  )
}

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
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

function LogoutButton() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [pending, setPending] = useState(false)

  return (
    <button
      type="button"
      disabled={pending}
      className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm text-zinc-400 hover:bg-white/5 hover:text-zinc-100 disabled:opacity-40"
      onClick={() => {
        setPending(true)
        void logout()
          .then(async () => {
            queryClient.clear()
            await navigate({ to: '/login' })
          })
          .catch((error: unknown) => {
            toast.error(errorMessage(error))
          })
          .finally(() => setPending(false))
      }}
    >
      <LogOut className="h-4 w-4" />
      Cerrar sesión
    </button>
  )
}
