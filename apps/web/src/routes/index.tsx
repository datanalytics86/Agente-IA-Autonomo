import { createFileRoute } from '@tanstack/react-router'
import { ActivityChart } from '../components/ActivityChart'
import { AgentsOverview } from '../components/AgentsOverview'
import { KpiGrid } from '../components/KpiGrid'
import { LiveLogs } from '../components/LiveLogs'
import { QuickActions } from '../components/QuickActions'

export const Route = createFileRoute('/')({
  component: PanelPage,
})

function PanelPage() {
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-50 sm:text-2xl">
          Panel de control
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Multiagente demo · landings para pymes locales en Chile
        </p>
      </header>

      <KpiGrid />
      <QuickActions />

      <div className="grid gap-5 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <ActivityChart />
        </div>
        <div className="xl:col-span-2">
          <LiveLogs limit={6} />
        </div>
      </div>

      <AgentsOverview compact />
    </div>
  )
}
