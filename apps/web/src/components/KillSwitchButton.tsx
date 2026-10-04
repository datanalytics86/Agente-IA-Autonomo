import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Power } from 'lucide-react'
import { toast } from 'sonner'
import { errorMessage } from '../api/http'
import {
  fetchSettings,
  isArmed,
  killSwitchLabel,
  putKillSwitch,
  SENDS_STOPPED_LABEL,
  settingsWithOnline,
} from '../api/settings'
import type { Settings } from '../api/types'
import { cn } from '../lib/cn'

export function KillSwitchButton({ variant = 'button' }: { variant?: 'button' | 'pill' }) {
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: fetchSettings })
  const mutation = useMutation({
    mutationFn: (online: boolean) => {
      const current = queryClient.getQueryData<Settings>(['settings']) ?? settings.data
      if (!current) throw new Error('No hay settings para actualizar')
      return putKillSwitch(online, current)
    },
    onSuccess: async (_data, online) => {
      queryClient.setQueryData<Settings>(['settings'], (current) =>
        current ? settingsWithOnline(current, online) : current,
      )
      await queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast.success(online ? 'Kill switch armado' : SENDS_STOPPED_LABEL)
    },
    onError: (error) => {
      toast.error(errorMessage(error))
    },
  })

  const armed = settings.data ? isArmed(settings.data) : false
  const label = settings.isPending
    ? '…'
    : settings.isError
      ? 'sin estado'
      : killSwitchLabel(settings.data ?? null)
  const disabled = !settings.data || mutation.isPending

  const className =
    variant === 'pill'
      ? cn(
          'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 disabled:opacity-50',
          settings.data && armed
            ? 'bg-accent/10 text-accent ring-accent/25'
            : settings.data
              ? 'bg-amber-500/10 text-amber-200 ring-amber-500/25'
              : 'bg-white/5 text-zinc-400 ring-white/10',
        )
      : cn(
          'mt-4 flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition disabled:opacity-50',
          settings.data && armed
            ? 'border-accent/30 bg-accent/10 text-accent hover:bg-accent/15'
            : settings.data
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/15'
              : 'border-white/10 bg-white/5 text-zinc-400',
        )

  return (
    <button
      type="button"
      className={className}
      disabled={disabled}
      aria-pressed={settings.data ? armed : undefined}
      title="Enciende o detiene los envíos en el motor"
      onClick={() => {
        if (!settings.data) return
        mutation.mutate(!isArmed(settings.data))
      }}
    >
      {variant === 'pill' ? (
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            settings.data && armed ? 'bg-accent' : 'bg-amber-400',
          )}
        />
      ) : (
        <Power className="h-4 w-4" />
      )}
      {label}
    </button>
  )
}
