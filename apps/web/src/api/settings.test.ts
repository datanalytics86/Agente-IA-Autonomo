import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SENDS_STOPPED_LABEL,
  isArmed,
  killSwitchLabel,
  putKillSwitch,
  sendsStopped,
  settingsWithOnline,
} from './settings'
import type { Settings } from './types'

const current: Settings = {
  kill_switch: false,
  app_mode: 'demo',
  quotas: { email: 15 },
  prices: { landing_esencial: 250_000 },
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('mapeo del kill switch', () => {
  it('online arma y apagado muestra envíos detenidos sin tocar el modo', () => {
    const armed = settingsWithOnline(current, true)
    const stopped = settingsWithOnline({ ...current, kill_switch: true, app_mode: 'prod' }, false)

    expect(armed.kill_switch).toBe(true)
    expect(armed.app_mode).toBe('demo')
    expect(armed.quotas).toEqual({ email: 15 })
    expect(isArmed(armed)).toBe(true)
    expect(sendsStopped(armed)).toBe(false)
    expect(killSwitchLabel(armed)).toBe('Online')

    expect(stopped.kill_switch).toBe(false)
    expect(stopped.app_mode).toBe('prod')
    expect(sendsStopped(stopped)).toBe(true)
    expect(killSwitchLabel(stopped)).toBe(SENDS_STOPPED_LABEL)
    expect(SENDS_STOPPED_LABEL).toBe('envíos detenidos')
  })

  it('PUT manda kill_switch y el CSRF de la cookie', async () => {
    const fetchMock = vi.fn(async () => json({ kill_switch: true, app_mode: 'demo' }))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('document', { cookie: 'session=httponly; csrf_token=abc123' })

    await putKillSwitch(true, current)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    const body = JSON.parse(String(init.body)) as Settings

    expect(url).toBe('/api/settings')
    expect(init.method).toBe('PUT')
    expect(init.credentials).toBe('include')
    expect(headers.get('X-CSRF-Token')).toBe('abc123')
    expect(body.kill_switch).toBe(true)
    expect(body.app_mode).toBe('demo')
    expect(body.quotas).toEqual({ email: 15 })
    expect(body.prices).toEqual({ landing_esencial: 250_000 })
  })

  it('apagar el switch deja kill_switch en false', async () => {
    const fetchMock = vi.fn(async () => json({}))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('document', { cookie: 'csrf_token=tok' })

    await putKillSwitch(false, { ...current, kill_switch: true })

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    const body = JSON.parse(String(init.body)) as { kill_switch: boolean }
    expect(body.kill_switch).toBe(false)
    expect(sendsStopped(body)).toBe(true)
    expect(killSwitchLabel(body)).toBe('envíos detenidos')
  })
})
