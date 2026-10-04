import { apiFetch } from './http'
import type { Settings } from './types'

/** ADR-005: kill_switch true arma los envíos. false los deja detenidos. */
export const SENDS_STOPPED_LABEL = 'envíos detenidos'

export function isArmed(settings: { kill_switch: boolean }): boolean {
  return settings.kill_switch === true
}

export function sendsStopped(settings: { kill_switch: boolean }): boolean {
  return settings.kill_switch !== true
}

export function killSwitchLabel(settings: { kill_switch: boolean } | null): string {
  if (!settings) return 'sin estado'
  return sendsStopped(settings) ? SENDS_STOPPED_LABEL : 'Online'
}

export function settingsWithOnline(current: Settings, online: boolean): Settings {
  return {
    ...current,
    kill_switch: online,
    app_mode: current.app_mode,
  }
}

export async function fetchSettings(): Promise<Settings> {
  return apiFetch<Settings>('/api/settings')
}

export async function putSettings(body: Settings): Promise<void> {
  await apiFetch<unknown>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function putKillSwitch(online: boolean, current: Settings): Promise<void> {
  await putSettings(settingsWithOnline(current, online))
}
