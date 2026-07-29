const clpFormatter = new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0,
})

const usdFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

/** Aprox. 930 CLP = 1 USD (demo) */
export const CLP_PER_USD = 930

export function formatClp(value: number): string {
  return clpFormatter.format(value)
}

export function formatUsd(value: number): string {
  return usdFormatter.format(value)
}

export function clpToUsd(clp: number): number {
  return Math.round(clp / CLP_PER_USD)
}

export function shortId(id: string): string {
  return id.length > 12 ? id.slice(-10) : id
}

export function formatTs(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-CL', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
