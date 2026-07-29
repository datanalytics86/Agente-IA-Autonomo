export type LeadStatus =
  | 'nuevo'
  | 'diagnosticado'
  | 'landing'
  | 'video'
  | 'pitch_listo'
  | 'enviado'
  | 'respondio'
  | 'agendado'
  | 'cerrado'
  | 'revision'

export type AgentName =
  | 'Orchestrator'
  | 'Scout'
  | 'Diagnoser'
  | 'Builder'
  | 'Filmer'
  | 'Checker'
  | 'Pitcher'
  | 'Mobile'

export type AgentRuntimeStatus = 'idle' | 'running' | 'waiting' | 'offline'

export type LogLevel = 'info' | 'warn' | 'error' | 'success'

export interface Lead {
  id: string
  business: string
  category: string
  city: string
  commune: string
  hasWebsite: boolean
  websiteYear?: number
  rating: number
  reviews: number
  status: LeadStatus
  estimatedValueClp: number
  diagnosis?: string
  pitch?: string
  reason?: string
  highValue: boolean
  channels: string[]
  contactHint?: string
  createdAt: string
  updatedAt: string
}

export interface LogEntry {
  id: string
  ts: string
  agent: AgentName | string
  message: string
  level: LogLevel
}

export interface AgentInfo {
  name: AgentName
  role: string
  status: AgentRuntimeStatus
}

export interface DayActivity {
  day: string
  leads: number
  mensajes: number
  respuestas: number
}

export const STATUS_FLOW: LeadStatus[] = [
  'nuevo',
  'diagnosticado',
  'landing',
  'video',
  'pitch_listo',
  'enviado',
  'respondio',
  'agendado',
  'cerrado',
]

export const STATUS_LABELS: Record<LeadStatus, string> = {
  nuevo: 'Nuevo',
  diagnosticado: 'Diagnosticado',
  landing: 'Landing',
  video: 'Video',
  pitch_listo: 'Pitch listo',
  enviado: 'Enviado',
  respondio: 'Respondió',
  agendado: 'Agendado',
  cerrado: 'Cerrado',
  revision: 'Revisión HITL',
}

export const PIPELINE_STATUSES: LeadStatus[] = [
  'nuevo',
  'diagnosticado',
  'landing',
  'video',
  'pitch_listo',
  'enviado',
  'respondio',
  'agendado',
  'revision',
]
