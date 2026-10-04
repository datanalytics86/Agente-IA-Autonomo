export type PackageCode =
  | 'landing_esencial'
  | 'landing_pro'
  | 'landing_premium'
  | 'multi_sede';

export interface PackageInfo {
  code: PackageCode;
  name: string;
  priceClp: number | null;
  priceLabel: string;
  revisions: string;
  includes: string[];
  summary: string;
}

export const packages: PackageInfo[] = [
  {
    code: 'landing_esencial',
    name: 'Esencial',
    priceClp: 250000,
    priceLabel: '250.000 CLP',
    revisions: '1',
    summary: 'Una landing de cinco secciones, publicada, con una ronda de revisión.',
    includes: [
      'Landing de 5 secciones',
      'Publicación en el dominio del cliente o en un subdominio',
      '1 ronda de revisión',
    ],
  },
  {
    code: 'landing_pro',
    name: 'Pro',
    priceClp: 350000,
    priceLabel: '350.000 CLP',
    revisions: '2',
    summary: 'Lo esencial, más un video vertical, formulario y WhatsApp del cliente.',
    includes: [
      'Todo lo del Esencial',
      'Video vertical de 12 segundos',
      'Formulario de contacto',
      'Botón de WhatsApp con el número del cliente',
      '2 rondas de revisión',
    ],
  },
  {
    code: 'landing_premium',
    name: 'Premium',
    priceClp: 450000,
    priceLabel: '450.000 CLP',
    revisions: '3',
    summary: 'Lo pro, más SEO local básico y datos estructurados con información real.',
    includes: [
      'Todo lo del Pro',
      'SEO local básico',
      'schema.org solo con datos reales del negocio',
      '3 rondas de revisión',
    ],
  },
  {
    code: 'multi_sede',
    name: 'Multi sede',
    priceClp: null,
    priceLabel: 'a cotizar',
    revisions: 'según cotización',
    summary: 'Varias sucursales. No tiene precio cerrado y lo revisa una persona antes de proponerse.',
    includes: [
      'Alcance a definir según sucursales',
      'Siempre pasa por revisión humana',
      'Sin cobro automático en esta página',
    ],
  },
];

export function findPackage(code: string): PackageInfo | undefined {
  return packages.find((item) => item.code === code);
}
