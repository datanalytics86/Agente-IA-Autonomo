import { asRecord, field } from '../lib/records'
import { ApiError, apiFetch } from './http'
import type {
  AgentStatus,
  Approval,
  DataRequestEntry,
  EventLog,
  LeadDetail,
  LeadPage,
  Message,
  Order,
  Project,
  SuppressionEntry,
  Thread,
  User,
} from './types'

export const MANUAL_ACTIONS = ['scout', 'cycle', 'followups', 'digest'] as const
export type ManualAction = (typeof MANUAL_ACTIONS)[number]

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

function asList(data: unknown, label: string): unknown[] {
  if (Array.isArray(data)) return data
  const record = asRecord(data)
  if (record && Array.isArray(record.items)) return record.items
  throw new ApiError(200, `La API respondió un formato de ${label} no reconocido`, 'invalid_shape')
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/api/auth/me')
}

export function login(email: string, password: string): Promise<User> {
  return apiFetch<User>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function logout(): Promise<void> {
  await apiFetch<unknown>('/api/auth/logout', { method: 'POST' })
}

export async function fetchLeads(params: {
  status?: string
  q?: string
  page?: number
  page_size?: number
}): Promise<LeadPage> {
  const data = await apiFetch<LeadPage>(`/api/leads${queryString(params)}`)
  if (!data || !Array.isArray(data.items) || typeof data.total !== 'number') {
    throw new ApiError(200, 'La API respondió un listado de leads inválido', 'invalid_shape')
  }
  return data
}

export function fetchLead(id: string): Promise<LeadDetail> {
  return apiFetch<LeadDetail>(`/api/leads/${encodeURIComponent(id)}`)
}

export async function fetchApprovals(status = 'pending'): Promise<Approval[]> {
  const data = await apiFetch<unknown>(`/api/approvals${queryString({ status })}`)
  return asList(data, 'aprobaciones') as Approval[]
}

export async function approveHitl(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/approvals/${encodeURIComponent(id)}/approve`, { method: 'POST' })
}

export async function rejectHitl(id: string, note: string): Promise<void> {
  await apiFetch<unknown>(`/api/approvals/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export async function editHitl(
  id: string,
  body: { body_text: string; subject: string },
): Promise<void> {
  await apiFetch<unknown>(`/api/approvals/${encodeURIComponent(id)}/edit`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function fetchManualQueue(): Promise<Message[]> {
  const data = await apiFetch<unknown>('/api/manual-queue')
  return asList(data, 'cola manual') as Message[]
}

export async function markManualSent(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/manual-queue/${encodeURIComponent(id)}/mark-sent`, {
    method: 'POST',
  })
}

export async function fetchThreads(): Promise<Thread[]> {
  const data = await apiFetch<unknown>('/api/conversations')
  return asList(data, 'conversaciones') as Thread[]
}

export async function fetchMessages(leadId: string): Promise<Message[]> {
  const data = await apiFetch<unknown>(`/api/messages${queryString({ lead_id: leadId })}`)
  return asList(data, 'mensajes') as Message[]
}

export async function replyThread(id: string, bodyText: string): Promise<void> {
  await apiFetch<unknown>(`/api/conversations/${encodeURIComponent(id)}/reply`, {
    method: 'POST',
    body: JSON.stringify({ body_text: bodyText }),
  })
}

export async function fetchAgents(): Promise<AgentStatus[]> {
  const data = await apiFetch<unknown>('/api/agents')
  return asList(data, 'agentes') as AgentStatus[]
}

export async function enqueueAction(name: ManualAction): Promise<void> {
  await apiFetch<unknown>(`/api/actions/${name}`, { method: 'POST' })
}

export async function fetchEvents(params: {
  level?: string
  agent?: string
  limit?: number
}): Promise<EventLog[]> {
  const data = await apiFetch<unknown>(`/api/events${queryString(params)}`)
  return asList(data, 'eventos') as EventLog[]
}

export async function fetchOrders(): Promise<Order[]> {
  const data = await apiFetch<unknown>('/api/orders')
  return asList(data, 'pedidos') as Order[]
}

export async function fetchProjects(): Promise<Project[]> {
  const data = await apiFetch<unknown>('/api/projects')
  return asList(data, 'proyectos') as Project[]
}

export async function fetchSuppression(): Promise<SuppressionEntry[]> {
  const data = await apiFetch<unknown>('/api/compliance/suppression')
  return asList(data, 'supresión').map((item, index) => {
    const record = asRecord(item)
    const id = field(record, 'id')
    const kind = field(record, 'kind')
    const valueHash = field(record, 'value_hash')
    if (!id || !kind || !valueHash) {
      throw new ApiError(200, `Supresión ${index + 1} sin id, kind o value_hash`, 'invalid_shape')
    }
    return {
      id,
      kind,
      value_hash: valueHash,
      reason: field(record, 'reason') ?? undefined,
      source: field(record, 'source') ?? undefined,
      created_at: field(record, 'created_at') ?? undefined,
    }
  })
}

export async function addSuppression(body: {
  kind: string
  value: string
  reason: string
}): Promise<void> {
  await apiFetch<unknown>('/api/compliance/suppression', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function deleteSuppression(id: string): Promise<void> {
  await apiFetch<unknown>(`/api/compliance/suppression${queryString({ id })}`, {
    method: 'DELETE',
  })
}

export async function fetchDataRequests(): Promise<DataRequestEntry[]> {
  const data = await apiFetch<unknown>('/api/compliance/data-requests')
  return asList(data, 'solicitudes de derechos').map((item, index) => {
    const record = asRecord(item)
    const id = field(record, 'id')
    const kind = field(record, 'kind')
    const status = field(record, 'status')
    if (!id || !kind || !status) {
      throw new ApiError(200, `Solicitud ${index + 1} sin id, kind o status`, 'invalid_shape')
    }
    return {
      id,
      kind,
      status,
      requester_email: field(record, 'requester_email') ?? undefined,
      details: field(record, 'details') ?? undefined,
      due_at: field(record, 'due_at') ?? undefined,
      resolved_at: field(record, 'resolved_at'),
    }
  })
}

export async function patchDataRequest(id: string, status: string): Promise<void> {
  await apiFetch<unknown>('/api/compliance/data-requests', {
    method: 'PATCH',
    body: JSON.stringify({ id, status }),
  })
}
