export interface FaqItem {
  question: string;
  answer: string;
}

export const faq: FaqItem[] = [
  {
    question: '¿El diagnóstico gratis obliga a contratar?',
    answer:
      'No. Dejas los datos del negocio y te llegará el informe por email. Elegir un paquete y pagar es otro paso.',
  },
  {
    question: '¿Cuánto cuestan los paquetes?',
    answer:
      'Esencial 250.000 CLP, Pro 350.000 CLP y Premium 450.000 CLP. Multi sede es a cotizar. El anticipo es 50 % y el saldo se paga antes de publicar.',
  },
  {
    question: '¿Los precios incluyen IVA?',
    answer:
      'Por defecto los precios publicados incluyen IVA de 19 %. El documento tributario, boleta o factura, se emite aparte: esta web no lo genera.',
  },
  {
    question: '¿En cuántos días está lista la landing?',
    answer:
      'No publicamos un plazo fijo. Depende del paquete, de tus textos y de las rondas de revisión. La propuesta concreta la fecha; esta página no la promete.',
  },
  {
    question: '¿Publican opiniones de clientes?',
    answer:
      'No. aún no publicamos testimonios. Tampoco inventamos cifras, logos ni garantías de venta.',
  },
  {
    question: '¿Hay una página por comuna?',
    answer:
      'No. Hay una página por rubro, cada una con un criterio distinto. No armamos páginas masivas por comuna.',
  },
  {
    question: '¿Puedo pedir que no me escriban?',
    answer:
      'Sí. La Ley 19.496, artículo 28 B, exige identificar al remitente y dar una dirección válida para no recibir más publicidad. Esa dirección es la página Baja. Pedida la baja, no se vuelve a enviar.',
  },
  {
    question: '¿El sitio usa cookies de publicidad?',
    answer:
      'No. No cargamos analítica con cookies ni cookies de terceros. El calendario de la página Agendar solo aparece si se configuró un enlace; si no, la página lo dice y no simula una agenda.',
  },
];
