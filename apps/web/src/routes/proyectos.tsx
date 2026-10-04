import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { fetchOrders, fetchProjects } from '../api/endpoints'
import { PageHeader } from '../components/PageHeader'
import { QueryState } from '../components/QueryState'
import { formatClp } from '../lib/format'
import { cardClass } from '../lib/ui'

export const Route = createFileRoute('/proyectos')({
  component: ProyectosPage,
})

function ProyectosPage() {
  const orders = useQuery({ queryKey: ['orders'], queryFn: fetchOrders })
  const projects = useQuery({ queryKey: ['projects'], queryFn: fetchProjects })

  return (
    <div className="space-y-5">
      <PageHeader
        title="Proyectos y pedidos"
        subtitle="Estado de entrega, revisiones y totales del pedido. El ingreso del mes está solo en el panel."
      />
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-zinc-100">Pedidos</h2>
        <QueryState
          isPending={orders.isPending}
          error={orders.error}
          isEmpty={orders.data?.length === 0}
          empty="No hay pedidos"
        >
          <div className="space-y-3">
            {(orders.data ?? []).map((order) => (
              <article key={order.id} className={cardClass}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-zinc-100">{order.package_code ?? order.id}</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {order.status}
                      {order.lead_id ? ` · lead ${order.lead_id}` : ''}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-zinc-200">{formatClp(order.total_clp)}</p>
                </div>
                <p className="mt-2 text-[11px] text-zinc-500">Total del pedido, no ingreso cobrado.</p>
              </article>
            ))}
          </div>
        </QueryState>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-zinc-100">Proyectos</h2>
        <QueryState
          isPending={projects.isPending}
          error={projects.error}
          isEmpty={projects.data?.length === 0}
          empty="No hay proyectos"
        >
          <div className="space-y-3">
            {(projects.data ?? []).map((project) => (
              <article key={project.id} className={cardClass}>
                <p className="text-sm font-semibold text-zinc-100">{project.status}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  Revisiones {project.revisions_used ?? 0}
                  {typeof project.max_revisions === 'number' ? ` / ${project.max_revisions}` : ''}
                </p>
                {project.domain && <p className="mt-2 break-words text-sm text-zinc-300">{project.domain}</p>}
                {project.deploy_url && (
                  <a
                    href={project.deploy_url}
                    className="mt-2 block break-all text-sm text-accent"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {project.deploy_url}
                  </a>
                )}
              </article>
            ))}
          </div>
        </QueryState>
      </section>
    </div>
  )
}
