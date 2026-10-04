import { asRecord, asString } from '../lib/records'

const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  readonly status: number
  readonly code: string | undefined

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Error inesperado'
}

export function readCookie(name: string, source?: string): string | null {
  const raw = source ?? (typeof document === 'undefined' ? '' : document.cookie)
  if (!raw) return null
  for (const part of raw.split(';')) {
    const trimmed = part.trim()
    const eq = trimmed.indexOf('=')
    if (eq <= 0) continue
    if (trimmed.slice(0, eq) !== name) continue
    const value = trimmed.slice(eq + 1)
    try {
      return decodeURIComponent(value)
    } catch {
      return value
    }
  }
  return null
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (MUTATING.has(method)) {
    const token = readCookie('csrf_token')
    if (token) headers.set('X-CSRF-Token', token)
  }

  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      method,
      headers,
      credentials: 'include',
      cache: 'no-store',
    })
  } catch {
    throw new ApiError(0, 'No se pudo contactar la API', 'network')
  }

  if (response.status === 204 || response.status === 205) return undefined as T

  const text = await response.text()
  let data: unknown
  if (text) {
    try {
      data = JSON.parse(text) as unknown
    } catch {
      if (!response.ok) throw new ApiError(response.status, `Error ${response.status}`)
      throw new ApiError(response.status, 'La API respondió un JSON inválido', 'invalid_json')
    }
  }

  if (!response.ok) {
    const body = asRecord(data)
    const nested = asRecord(body?.error)
    throw new ApiError(
      response.status,
      asString(nested?.message) ?? `Error ${response.status}`,
      asString(nested?.code) ?? undefined,
    )
  }

  return data as T
}
