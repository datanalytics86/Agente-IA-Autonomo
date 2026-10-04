import { createFileRoute } from '@tanstack/react-router'
import { LiveLogs } from '../components/LiveLogs'
import { PageHeader } from '../components/PageHeader'

export const Route = createFileRoute('/logs')({
  component: LogsPage,
})

function LogsPage() {
  return (
    <div className="space-y-5">
      <PageHeader title="Logs" subtitle="Eventos del motor, con filtro y stream cuando la API está arriba." />
      <LiveLogs limit={100} showFilters />
    </div>
  )
}
