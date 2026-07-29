import { createFileRoute } from '@tanstack/react-router'
import { LiveLogs } from '../components/LiveLogs'
import { useAgencyStore } from '../store/useAgencyStore'

export const Route = createFileRoute('/logs')({
  component: LogsPage,
})

function LogsPage() {
  const total = useAgencyStore((s) => s.logs.length)

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Logs</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Historial de actividad multiagente · {total} eventos
        </p>
      </header>
      <LiveLogs limit={50} />
    </div>
  )
}
