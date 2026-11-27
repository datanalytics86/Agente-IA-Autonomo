import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import test from 'node:test';

const root = join(import.meta.dirname, '..', 'dist');

const rubros = [
  ['clinica-dental', 'Clínica dental'],
  ['optica', 'Óptica'],
  ['abogados', 'Estudio de abogados'],
  ['estudio-contable', 'Estudio contable'],
  ['peluqueria', 'Peluquería'],
  ['centro-estetica', 'Centro de estética'],
  ['spa', 'Spa y masajes'],
  ['gimnasio', 'Gimnasio boutique'],
  ['cafeteria', 'Cafetería'],
  ['restaurante', 'Restaurante de barrio'],
  ['taller-mecanico', 'Taller mecánico'],
  ['inmobiliaria', 'Inmobiliaria local'],
  ['veterinaria', 'Veterinaria'],
  ['escuela-idiomas', 'Escuela de idiomas'],
  ['ferreteria', 'Ferretería'],
];

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) files.push(...(await walk(path)));
    else files.push(path);
  }
  return files;
}

async function html() {
  const files = (await walk(root)).filter((file) => file.endsWith('.html'));
  assert.ok(files.length > 0, 'No hay HTML. Corre npm.cmd run build antes de npm.cmd test.');
  let source = '';
  for (const file of files) source += await readFile(file, 'utf8');
  return source;
}

const legalPages = ['privacidad', 'terminos', 'baja', 'derechos'];

const identity = [
  'DEEP PRO CONSULTORES SpA',
  'DEEP PRO BUSINESS SOLUTIONS SpA',
  '77.923.111-9',
  'Antonio Bellet 193, of. 1210, Providencia',
  'Nicolás Andrade Socías',
  'nicolas.andrade@deeppro.cl',
];

test('el footer y cada página legal muestran la identidad de Deep Pro', async () => {
  const home = await readFile(join(root, 'index.html'), 'utf8');
  const footer = home.match(/<footer[\s\S]*<\/footer>/)?.[0] ?? '';
  for (const value of identity) assert.match(footer, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(home, /property="og:site_name" content="DEEP PRO CONSULTORES SpA"/);
  for (const page of legalPages) {
    const htmlPage = await readFile(join(root, page, 'index.html'), 'utf8');
    for (const value of identity) {
      assert.match(htmlPage, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), page);
    }
  }
  assert.equal(home.includes('T14'), false);
});

const ALLOWED_RUT = '77.923.111-9';
const RUT_RE = /\b\d{1,2}[.\s]?\d{3}[.\s]?\d{3}\s*-\s*[\dkK]\b/g;
const PHONE_RE =
  /(?:\+?56[\s.-]*)?\b(?:9[\s.-]*\d{4}[\s.-]*\d{4}|2[\s.-]*\d{4}[\s.-]*\d{4}|[2-7]\d[\s.-]*\d{3}[\s.-]*\d{4})\b/g;

function normalizeRut(value) {
  return value.replace(/[.\s]/g, '');
}

function assertPublicContact(source) {
  const allowed = normalizeRut(ALLOWED_RUT);
  const ruts = source.match(RUT_RE) ?? [];
  for (const rut of ruts) {
    if (normalizeRut(rut) !== allowed) {
      throw new Error(`RUT no permitido: ${rut}`);
    }
  }
  const phones = source.match(PHONE_RE) ?? [];
  if (phones.length > 0) {
    throw new Error(`teléfono chileno: ${phones.join(', ')}`);
  }
}

test('el build solo publica el RUT de la agencia y ningún teléfono', async () => {
  assertPublicContact(await html());
});

test('un RUT ajeno falla el guardrail', () => {
  assert.throws(
    () => assertPublicContact(`dato 12.345.678-5 y ${ALLOWED_RUT}`),
    /RUT no permitido: 12\.345\.678-5/,
  );
  for (const sample of ['912345678', '9-1234-5678', '12345678-5', '12 345 678-5']) {
    assert.throws(() => assertPublicContact(sample), /RUT no permitido|teléfono chileno/, sample);
  }
  for (const sample of ['+56 2 2345 6789', '223456789', '+56 32 123 4567', '32 123 4567']) {
    assert.throws(() => assertPublicContact(sample), /teléfono chileno/, sample);
  }
});

test('textos públicos obligatorios y precios', async () => {
  const source = await html();
  assert.match(source, /aún no publicamos testimonios/);
  assert.match(source, /te llegará el informe por email/);
  assert.match(source, /250\.000 CLP/);
  assert.match(source, /350\.000 CLP/);
  assert.match(source, /450\.000 CLP/);
  assert.match(source, /a cotizar/);
  assert.match(source, /Ley 21\.719/);
  assert.match(source, /Ley 19\.628/);
  assert.match(source, /artículo 28 B/);
  assert.match(source, /lang="es-CL"/);
  assert.match(source, /ProfessionalService/);
  assert.doesNotMatch(source, /fonts\.googleapis|googletagmanager|google-analytics|connect\.facebook|hotjar/);
});

test('JSON-LD ProfessionalService no inventa address', async () => {
  const source = await html();
  const blocks = [
    ...source.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g),
  ];
  assert.ok(blocks.length > 0);
  const configuredAddress = (
    process.env.PUBLIC_AGENCY_ADDRESS ||
    process.env.AGENCY_ADDRESS ||
    ''
  ).trim();
  for (const block of blocks) {
    const data = JSON.parse(block[1]);
    assert.equal(data['@type'], 'ProfessionalService');
    const configuredName = (
      process.env.PUBLIC_AGENCY_NAME ||
      process.env.AGENCY_NAME ||
      'DEEP PRO CONSULTORES SpA'
    ).trim();
    const configuredLegal = (
      process.env.PUBLIC_AGENCY_LEGAL_NAME ||
      process.env.AGENCY_LEGAL_NAME ||
      'DEEP PRO BUSINESS SOLUTIONS SpA'
    ).trim();
    assert.equal(data.name, configuredName);
    assert.equal(data.legalName, configuredLegal);
    const street = configuredAddress || 'Antonio Bellet 193, of. 1210, Providencia';
    assert.equal(data.address.streetAddress, street);
  }
});

test('robots bloquea demo, proyecto y u', async () => {
  const robots = await readFile(join(root, 'robots.txt'), 'utf8');
  assert.match(robots, /Disallow:\s*\/demo/);
  assert.match(robots, /Disallow:\s*\/proyecto/);
  assert.match(robots, /Disallow:\s*\/u/);
  await readFile(join(root, 'sitemap-index.xml'), 'utf8');
});

test('el portal es noindex y los 15 rubros no son la misma página', async () => {
  const portal = await readFile(join(root, 'proyecto', 'shell', 'index.html'), 'utf8');
  assert.match(portal, /noindex/);
  assert.match(portal, /Intake/);
  assert.match(portal, /Vista previa/);
  assert.match(portal, /Feedback/);
  assert.match(portal, /Aprobar/);

  const mains = [];
  for (const [slug, label] of rubros) {
    const page = await readFile(join(root, 'rubros', slug, 'index.html'), 'utf8');
    const main = page.match(/<main[\s\S]*<\/main>/)?.[0] ?? page;
    const normalized = main.replaceAll(slug, '').replaceAll(label, '').replace(/\s+/g, ' ').trim();
    mains.push(normalized);
  }
  assert.equal(new Set(mains).size, rubros.length);
  const entries = await readdir(root, { withFileTypes: true });
  assert.equal(
    entries.some((entry) => entry.name.toLowerCase().includes('comuna')),
    false,
  );
});
