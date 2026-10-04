export const LEAD_STATUSES = [
  'nuevo',
  'diagnosticado',
  'landing',
  'video',
  'pitch_listo',
  'enviado',
  'respondio',
  'agendado',
  'propuesta',
  'pagado',
  'en_produccion',
  'en_revision_cliente',
  'entregado',
  'postventa',
  'revision',
  'perdido',
  'opt_out',
] as const

const LABELS: Record<string, string> = {
  nuevo: 'Nuevo',
  diagnosticado: 'Diagnosticado',
  landing: 'Landing',
  video: 'Video',
  pitch_listo: 'Pitch listo',
  enviado: 'Enviado',
  respondio: 'Respondió',
  agendado: 'Agendado',
  propuesta: 'Propuesta',
  pagado: 'Pagado',
  en_produccion: 'En producción',
  en_revision_cliente: 'Revisión del cliente',
  entregado: 'Entregado',
  postventa: 'Postventa',
  revision: 'Revisión HITL',
  perdido: 'Perdido',
  opt_out: 'Opt-out',
}

export function leadStatusLabel(status: string): string {
  return LABELS[status] ?? status
}
