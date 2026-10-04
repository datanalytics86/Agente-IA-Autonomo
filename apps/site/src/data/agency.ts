import { assertProdIdentity } from './prod-identity.mjs';

assertProdIdentity();

export const IDENTITY_PLACEHOLDER = '[datos de la agencia]';

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
  return value.length > 0 && value !== IDENTITY_PLACEHOLDER;
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
  name: first(process.env.PUBLIC_AGENCY_NAME, process.env.AGENCY_NAME) || IDENTITY_PLACEHOLDER,
  legalName:
    first(process.env.PUBLIC_AGENCY_LEGAL_NAME, process.env.AGENCY_LEGAL_NAME) ||
    IDENTITY_PLACEHOLDER,
  rut: first(process.env.PUBLIC_AGENCY_RUT, process.env.AGENCY_RUT) || IDENTITY_PLACEHOLDER,
  email: first(process.env.PUBLIC_AGENCY_EMAIL, process.env.AGENCY_EMAIL) || IDENTITY_PLACEHOLDER,
  address: first(process.env.PUBLIC_AGENCY_ADDRESS, process.env.AGENCY_ADDRESS),
};

export const bookingLink = safeHttpUrl(process.env.PUBLIC_BOOKING_LINK);

export function publicApiBase(): string {
  return safeHttpUrl(process.env.PUBLIC_API_BASE)?.replace(/\/$/, '') ?? '';
}
