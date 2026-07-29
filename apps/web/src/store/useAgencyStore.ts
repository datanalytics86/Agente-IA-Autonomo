import { create } from 'zustand'
import {
  INITIAL_ACTIVITY,
  INITIAL_AGENTS,
  INITIAL_LEADS,
  INITIAL_LOGS,
  SCOUT_POOL,
} from '../lib/mock'
import type {
  AgentInfo,
  AgentName,
  AgentRuntimeStatus,
  DayActivity,
  Lead,
  LeadStatus,
  LogEntry,
  LogLevel,
} from '../lib/types'
import { PIPELINE_STATUSES } from '../lib/types'
import { CLP_PER_USD } from '../lib/format'

function nowIso(): string {
  return new Date().toISOString()
}

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

const NEXT_STATUS: Partial<Record<LeadStatus, LeadStatus>> = {
  nuevo: 'diagnosticado',
  diagnosticado: 'landing',
  landing: 'video',
  video: 'pitch_listo',
  pitch_listo: 'enviado',
  enviado: 'respondio',
  respondio: 'agendado',
  agendado: 'cerrado',
  revision: 'pitch_listo',
}

interface AgencyState {
  systemOnline: boolean
  leads: Lead[]
  logs: LogEntry[]
  agents: AgentInfo[]
  activity: DayActivity[]
  messagesSentMonth: number
  tokensToday: number
  apiCostMonthUsd: number

  // derived helpers
  revenueMonthClp: () => number
  revenueMonthUsd: () => number
  apiCostMonthClp: () => number
  responseRate: () => number
  pipelineCount: () => number

  toggleSystem: () => void
  setAgentStatus: (name: AgentName, status: AgentRuntimeStatus) => void
  addLog: (agent: AgentName | string, message: string, level?: LogLevel) => void
  runScout: () => void
  runPitchBatch: () => void
  advanceLead: (id: string) => void
  approveLead: (id: string) => void
  rejectLead: (id: string) => void
}

export const useAgencyStore = create<AgencyState>((set, get) => ({
  systemOnline: true,
  leads: INITIAL_LEADS,
  logs: INITIAL_LOGS,
  agents: INITIAL_AGENTS,
  activity: INITIAL_ACTIVITY,
  messagesSentMonth: 37,
  tokensToday: 12_400,
  apiCostMonthUsd: 18.5,

  revenueMonthClp: () => {
    const closed = get().leads.filter((l) => l.status === 'cerrado' || l.status === 'agendado')
    const base = closed.reduce((s, l) => s + l.estimatedValueClp, 0)
    // ingresos demo: agendados/cerrados + 40% de enviados/respondio
    const mid = get()
      .leads.filter((l) => l.status === 'enviado' || l.status === 'respondio')
      .reduce((s, l) => s + Math.round(l.estimatedValueClp * 0.15), 0)
    return base + mid + 890_000
  },

  revenueMonthUsd: () => Math.round(get().revenueMonthClp() / CLP_PER_USD),

  apiCostMonthClp: () => Math.round(get().apiCostMonthUsd * CLP_PER_USD),

  responseRate: () => {
    const sent = get().leads.filter((l) =>
      ['enviado', 'respondio', 'agendado', 'cerrado'].includes(l.status),
    ).length
    const responded = get().leads.filter((l) =>
      ['respondio', 'agendado', 'cerrado'].includes(l.status),
    ).length
    if (sent === 0) return 0
    return Math.round((responded / sent) * 1000) / 10
  },

  pipelineCount: () =>
    get().leads.filter((l) => PIPELINE_STATUSES.includes(l.status) && l.status !== 'cerrado')
      .length,

  toggleSystem: () => {
    const online = !get().systemOnline
    set({
      systemOnline: online,
      agents: get().agents.map((a) => ({
        ...a,
        status: online ? 'idle' : 'offline',
      })),
    })
    get().addLog(
      'Orchestrator',
      online ? 'Sistema en línea' : 'Sistema en pausa (offline)',
      online ? 'success' : 'warn',
    )
  },

  setAgentStatus: (name, status) => {
    set({
      agents: get().agents.map((a) => (a.name === name ? { ...a, status } : a)),
    })
  },

  addLog: (agent, message, level = 'info') => {
    const entry: LogEntry = {
      id: uid('log'),
      ts: nowIso(),
      agent,
      message,
      level,
    }
    set({ logs: [entry, ...get().logs].slice(0, 200) })
  },

  runScout: () => {
    if (!get().systemOnline) {
      get().addLog('Scout', 'Sistema offline: no se puede correr Scout', 'error')
      return
    }
    get().setAgentStatus('Scout', 'running')
    get().setAgentStatus('Orchestrator', 'running')

    const existing = new Set(get().leads.map((l) => l.business.toLowerCase()))
    const pool = SCOUT_POOL.filter((p) => !existing.has(p.business.toLowerCase()))
    const n = 3 + Math.floor(Math.random() * 3) // 3–5
    const picked = (pool.length >= n ? pool : SCOUT_POOL)
      .sort(() => Math.random() - 0.5)
      .slice(0, n)

    const ts = nowIso()
    const newLeads: Lead[] = picked.map((p) => ({
      ...p,
      id: uid('lead'),
      status: 'nuevo' as const,
      highValue: p.estimatedValueClp >= 2_800_000,
      createdAt: ts,
      updatedAt: ts,
    }))

    set({
      leads: [...newLeads, ...get().leads],
      tokensToday: get().tokensToday + 800 + newLeads.length * 120,
      apiCostMonthUsd: get().apiCostMonthUsd + 0.4,
      activity: get().activity.map((d, i) =>
        i === get().activity.length - 1
          ? { ...d, leads: d.leads + newLeads.length }
          : d,
      ),
    })

    get().addLog(
      'Scout',
      `Scout OK · ${newLeads.length} leads nuevos (${newLeads.map((l) => l.commune).join(', ')})`,
      'success',
    )
    get().addLog('Orchestrator', 'Leads encolados en status nuevo', 'info')
    get().setAgentStatus('Scout', 'idle')
    get().setAgentStatus('Orchestrator', 'idle')
  },

  runPitchBatch: () => {
    if (!get().systemOnline) {
      get().addLog('Pitcher', 'Sistema offline: no se envían pitches', 'error')
      return
    }
    get().setAgentStatus('Pitcher', 'running')
    get().setAgentStatus('Checker', 'running')

    const ready = get().leads.filter((l) => l.status === 'pitch_listo' && !l.highValue)
    if (ready.length === 0) {
      get().addLog('Pitcher', 'No hay leads en pitch_listo para enviar', 'warn')
      get().setAgentStatus('Pitcher', 'idle')
      get().setAgentStatus('Checker', 'idle')
      return
    }

    const ids = new Set(ready.map((l) => l.id))
    const ts = nowIso()
    set({
      leads: get().leads.map((l) =>
        ids.has(l.id)
          ? {
              ...l,
              status: 'enviado' as const,
              updatedAt: ts,
              pitch:
                l.pitch ||
                `Hola ${l.business}: te preparé una landing demo. Responde STOP si no te interesa.`,
            }
          : l,
      ),
      messagesSentMonth: get().messagesSentMonth + ready.length,
      tokensToday: get().tokensToday + ready.length * 350,
      apiCostMonthUsd: get().apiCostMonthUsd + ready.length * 0.15,
      activity: get().activity.map((d, i) =>
        i === get().activity.length - 1
          ? { ...d, mensajes: d.mensajes + ready.length }
          : d,
      ),
    })

    get().addLog(
      'Checker',
      `${ready.length} pitches aprobados · opt-out STOP verificado`,
      'success',
    )
    get().addLog(
      'Pitcher',
      `Batch enviado (simulado) · ${ready.map((l) => l.business).join(', ')} · IG/email/LinkedIn`,
      'success',
    )
    get().setAgentStatus('Pitcher', 'idle')
    get().setAgentStatus('Checker', 'idle')
  },

  advanceLead: (id) => {
    if (!get().systemOnline) {
      get().addLog('Orchestrator', 'Sistema offline: no se avanza lead', 'error')
      return
    }
    const lead = get().leads.find((l) => l.id === id)
    if (!lead) return
    if (lead.status === 'cerrado') {
      get().addLog('Orchestrator', `${lead.business} ya está cerrado`, 'warn')
      return
    }
    if (lead.status === 'revision') {
      get().addLog(
        'Orchestrator',
        `${lead.business} en revisión HITL: usa Aprobar o Descartar`,
        'warn',
      )
      return
    }

    let next = NEXT_STATUS[lead.status]
    if (!next) return

    // High-value al llegar a pitch_listo o enviado → revision
    if (
      lead.estimatedValueClp >= 2_800_000 &&
      (next === 'pitch_listo' || next === 'enviado')
    ) {
      next = 'revision'
    }

    const ts = nowIso()
    const patch: Partial<Lead> = { status: next, updatedAt: ts }
    if (next === 'diagnosticado' && !lead.diagnosis) {
      patch.diagnosis = `Oportunidad en ${lead.commune}: ${lead.hasWebsite ? 'web desactualizada' : 'sin web'}. Paquete landing 250–450k CLP.`
    }
    if ((next === 'pitch_listo' || next === 'video') && !lead.pitch) {
      patch.pitch = `Hola ${lead.business}: armé una propuesta de landing para ${lead.category.toLowerCase()} en ${lead.commune}. ¿Te muestro el demo? Responde STOP para opt-out.`
    }
    if (next === 'revision') {
      patch.highValue = true
      patch.reason = `Deal ${lead.estimatedValueClp.toLocaleString('es-CL')} CLP → revisión manual (HITL)`
    }

    set({
      leads: get().leads.map((l) => (l.id === id ? { ...l, ...patch } : l)),
      tokensToday: get().tokensToday + 200,
    })
    get().addLog(
      'Orchestrator',
      `Avance · ${lead.business}: ${lead.status} → ${next}`,
      next === 'revision' ? 'warn' : 'info',
    )
  },

  approveLead: (id) => {
    const lead = get().leads.find((l) => l.id === id)
    if (!lead) return
    if (lead.status !== 'revision') {
      get().addLog('Orchestrator', `${lead.business} no está en revisión`, 'warn')
      return
    }
    const ts = nowIso()
    set({
      leads: get().leads.map((l) =>
        l.id === id
          ? {
              ...l,
              status: 'enviado' as const,
              highValue: true,
              updatedAt: ts,
              reason: (l.reason || '') + ' | Aprobado por humano',
            }
          : l,
      ),
      messagesSentMonth: get().messagesSentMonth + 1,
    })
    get().addLog(
      'Orchestrator',
      `HITL aprobado · ${lead.business} → enviado (simulado)`,
      'success',
    )
  },

  rejectLead: (id) => {
    const lead = get().leads.find((l) => l.id === id)
    if (!lead) return
    const ts = nowIso()
    set({
      leads: get().leads.map((l) =>
        l.id === id
          ? {
              ...l,
              status: 'cerrado' as const,
              updatedAt: ts,
              reason: (l.reason || '') + ' | Descartado',
            }
          : l,
      ),
    })
    get().addLog('Orchestrator', `Lead descartado · ${lead.business} → cerrado`, 'warn')
  },
}))

