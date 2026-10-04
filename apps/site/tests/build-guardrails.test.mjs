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

test('el build muestra el placeholder y no inventa un RUT', async () => {
  const source = await html();
  assert.match(source, /\[datos de la agencia\]/);
  assert.doesNotMatch(source, /\d{1,2}\.\d{3}\.\d{3}-[\dkK]/);
  assert.equal(source.includes('T14'), false);
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
    if (!configuredAddress) assert.equal(Object.hasOwn(data, 'address'), false);
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
