import type { components } from './schema'

export type Schemas = components['schemas']
export type Metrics = Schemas['Metrics']
export type Settings = Schemas['Settings']
export type User = Schemas['User']
export type Lead = Schemas['Lead']
export type LeadPage = Schemas['LeadPage']
export type LeadDetail = Schemas['LeadDetail']
export type Approval = Schemas['Approval']
export type Message = Schemas['Message']
export type Thread = Schemas['Thread']
export type AgentStatus = Schemas['AgentStatus']
export type EventLog = Schemas['Event']
export type Order = Schemas['Order']
export type Project = Schemas['Project']

export interface SuppressionEntry {
  id: string
  kind: string
  value_hash: string
  reason?: string
  source?: string
  created_at?: string
}

export interface DataRequestEntry {
  id: string
  kind: string
  status: string
  requester_email?: string
  details?: string
  due_at?: string
  resolved_at?: string | null
}
