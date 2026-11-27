export const AGENCY_NAME = 'DEEP PRO CONSULTORES SpA';
export const AGENCY_LEGAL_NAME = 'DEEP PRO BUSINESS SOLUTIONS SpA';
export const AGENCY_RUT = '77.923.111-9';
export const AGENCY_ADDRESS = 'Antonio Bellet 193, of. 1210, Providencia';
export const AGENCY_EMAIL = 'nicolas.andrade@deeppro.cl';
export const AGENCY_REPRESENTATIVE = 'Nicolás Andrade Socías';
export const PRIVACY_EMAIL_TODO = 'TODO(Deeppro): correo de privacidad';

function clean(value: string | undefined): string {
  return typeof value === 'string' ? value.trim() : '';
}

function first(...values: Array<string | undefined>): string {
  for (const value of values) {
    const trimmed = clean(value);
    if (trimmed) return trimmed;
  }
  return '';
}

export function isConfigured(value: string): boolean {
  return value.length > 0;
}

export function safeHttpUrl(value: string | undefined): string | null {
  const trimmed = clean(value);
  if (!trimmed) return null;
  try {
    const url = new URL(trimmed);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return url.href;
  } catch {
    return null;
  }
}

export const agency = {
  name: first(process.env.PUBLIC_AGENCY_NAME, process.env.AGENCY_NAME) || AGENCY_NAME,
  legalName:
    first(process.env.PUBLIC_AGENCY_LEGAL_NAME, process.env.AGENCY_LEGAL_NAME) ||
    AGENCY_LEGAL_NAME,
  rut: first(process.env.PUBLIC_AGENCY_RUT, process.env.AGENCY_RUT) || AGENCY_RUT,
  email: first(process.env.PUBLIC_AGENCY_EMAIL, process.env.AGENCY_EMAIL) || AGENCY_EMAIL,
  address: first(process.env.PUBLIC_AGENCY_ADDRESS, process.env.AGENCY_ADDRESS) || AGENCY_ADDRESS,
  representative: AGENCY_REPRESENTATIVE,
  privacyEmail: PRIVACY_EMAIL_TODO,
};

export const bookingLink = safeHttpUrl(process.env.PUBLIC_BOOKING_LINK);

export function publicApiBase(): string {
  return safeHttpUrl(process.env.PUBLIC_API_BASE)?.replace(/\/$/, '') ?? '';
}
