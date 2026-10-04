import { createFileRoute } from '@tanstack/react-router'
import { AgentsOverview } from '../components/AgentsOverview'
import { FunnelChart } from '../components/FunnelChart'
import { KpiGrid } from '../components/KpiGrid'
import { LiveLogs } from '../components/LiveLogs'
import { PageHeader } from '../components/PageHeader'
import { QuickActions } from '../components/QuickActions'

export const Route = createFileRoute('/')({
  component: PanelPage,
})

function PanelPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        title="Panel de control"
        subtitle="Indicadores de la API. Si el motor no responde, no se muestran cifras."
      />
      <KpiGrid />
      <QuickActions />
      <div className="grid gap-5 xl:grid-cols-5">
        <div className="min-w-0 xl:col-span-3">
          <FunnelChart />
        </div>
        <div className="min-w-0 xl:col-span-2">
          <LiveLogs limit={6} />
        </div>
      </div>
      <AgentsOverview compact />
    </div>
  )
}
