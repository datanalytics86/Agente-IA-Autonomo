import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, apiPath } from './http'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('llama /api en absoluto y no bajo /admin', async () => {
    const fetchMock = vi.fn(async () => new Response('null', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/leads')

    expect(apiPath('/api/leads?q=1')).toBe('/api/leads?q=1')
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/leads')
  })

  it('rechaza una ruta /admin/api', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiFetch('/admin/api/leads')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
