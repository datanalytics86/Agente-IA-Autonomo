export function prodIdentityError(env = process.env) {
  const flag = String(env.SITE_BUILD || '').trim().toLowerCase();
  if (flag !== 'prod') return '';
  const name = String(env.PUBLIC_AGENCY_NAME || env.AGENCY_NAME || '').trim();
  const email = String(env.PUBLIC_AGENCY_EMAIL || env.AGENCY_EMAIL || '').trim();
  const missing = [];
  if (!name) missing.push('AGENCY_NAME');
  if (!email) missing.push('AGENCY_EMAIL');
  if (missing.length === 0) return '';
  const listed = missing.join(' y ');
  return (
    `Build de producción del sitio: falta ${listed}. ` +
    `Define ${listed} antes de compilar con SITE_BUILD=prod.`
  );
}

export function assertProdIdentity(env = process.env) {
  const message = prodIdentityError(env);
  if (message) throw new Error(message);
}
