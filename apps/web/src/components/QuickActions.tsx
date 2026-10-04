import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Inbox, Radar, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { enqueueAction, fetchApprovals } from '../api/endpoints'
import { errorMessage } from '../api/http'
import { cardClass, primaryButtonClass, secondaryButtonClass } from '../lib/ui'

export function QuickActions() {
  const queryClient = useQueryClient()
  const approvals = useQuery({
    queryKey: ['approvals', 'pending'],
    queryFn: () => fetchApprovals('pending'),
  })
  const scout = useMutation({
    mutationFn: () => enqueueAction('scout'),
    onSuccess: async () => {
      toast.success('Scout encolado', { description: 'El navegador no envía mensajes.' })
      await queryClient.invalidateQueries({ queryKey: ['events'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <section className={cardClass}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">Acciones</h2>
        <p className="text-xs text-zinc-500">Encolan trabajo en la API. No marcan leads como enviados.</p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button
          type="button"
          className={primaryButtonClass}
          disabled={scout.isPending}
          onClick={() => scout.mutate()}
        >
          <Radar className="h-4 w-4" />
          Encolar scout
        </button>
        <Link to="/hitl" className={secondaryButtonClass}>
          <ShieldCheck className="h-4 w-4" />
          Bandeja HITL
          {approvals.data && (
            <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-[11px] font-semibold text-amber-200">
              {approvals.data.length}
            </span>
          )}
        </Link>
        <Link to="/manual" className={secondaryButtonClass}>
          <Inbox className="h-4 w-4" />
          Bandeja manual
        </Link>
      </div>
      {approvals.isError && (
        <p className="mt-3 text-xs text-rose-300">{errorMessage(approvals.error)}</p>
      )}
    </section>
  )
}
