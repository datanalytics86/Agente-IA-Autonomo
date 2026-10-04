export interface PortfolioExample {
  id: string;
  title: string;
  summary: string;
  points: string[];
  variant: 'carta' | 'taller' | 'estudio';
}

export const portfolio: PortfolioExample[] = [
  {
    id: 'cafeteria',
    title: 'Bosquejo de cafetería de barrio',
    summary:
      'Cinco bloques: qué se sirve, horario de la semana, cómo llegar, un aviso si el ítem se acaba y un contacto. No hay carta copiada ni foto de otro local.',
    points: ['La carta va antes que el relato', 'El horario distingue semana y fin de semana', 'Sin despacho si el local no despacha'],
    variant: 'carta',
  },
  {
    id: 'taller',
    title: 'Bosquejo de taller mecánico',
    summary:
      'La página dice qué vehículos entran, cómo se pide una revisión y dónde dejar el auto. No trae un precio «desde» para un repuesto que nadie cotizó.',
    points: ['Servicios con nombre, no «mecánica integral»', 'La cotización sale después de ver el auto', 'El mapa es el del taller, no un punto genérico'],
    variant: 'taller',
  },
  {
    id: 'contable',
    title: 'Bosquejo de estudio contable',
    summary:
      'Lista corta de trámites, documentos para la primera reunión y un calendario orientativo. No promete devolución de impuestos ni usa el logo del SII.',
    points: ['Cada trámite dice qué incluye y qué no', 'No se pide la clave tributaria en el formulario', 'El tono es de usted'],
    variant: 'estudio',
  },
];
