export function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

export function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

export function field(record: Record<string, unknown> | null, key: string): string | null {
  if (!record) return null
  const value = record[key]
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return asString(value)
}

export function manualProfileUrl(message: {
  channel: string
  check_result?: unknown
}): string | null {
  const record = asRecord(message.check_result)
  const direct =
    field(record, 'profile_url') ?? field(record, 'url') ?? field(record, 'linkedin_url')
  if (direct?.startsWith('https://')) return direct
  if (message.channel !== 'instagram') return null
  const handle = (field(record, 'instagram_handle') ?? field(record, 'handle'))?.replace(/^@/, '')
  if (!handle || !/^[A-Za-z0-9._]+$/.test(handle)) return null
  return `https://instagram.com/${handle}`
}

export function approvalDraft(payload: unknown): { subject: string; body_text: string } {
  const record = asRecord(payload)
  return {
    subject: field(record, 'subject') ?? '',
    body_text: field(record, 'body_text') ?? field(record, 'message') ?? '',
  }
}

export function approvalDiff(payload: unknown): string | null {
  const record = asRecord(payload)
  return field(record, 'diff') ?? field(record, 'body_diff')
}
