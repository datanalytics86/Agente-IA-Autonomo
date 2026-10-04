export interface RubroBlock {
  heading: string;
  paragraphs: string[];
  items?: string[];
}

export interface Rubro {
  slug: string;
  label: string;
  title: string;
  description: string;
  intro: string;
  blocks: RubroBlock[];
  related?: { slug: string; reason: string };
}

export const rubros: Rubro[] = [
  {
    slug: 'clinica-dental',
    label: 'Clínica dental',
    title: 'Landing para una clínica dental',
    description:
      'Qué debe decir el sitio de una clínica dental: hora, especialidad y cómo llegar, sin prometer un resultado clínico.',
    intro:
      'Una clínica dental no necesita un sitio largo. Necesita que una persona entienda, en un minuto, si usted atiende su caso, dónde está el box y cómo pide hora.',
    blocks: [
      {
        heading: 'Lo que la persona viene a saber',
        paragraphs: [
          'Antes de llamar quiere la comuna, el horario, si hay atención de urgencia el mismo día y qué especialidades cubre el equipo. Solo se listan las que de verdad se atienden. El teléfono va arriba, no después de una historia de la clínica.',
        ],
        items: [
          'Especialidades reales del equipo, no un listado genérico',
          'Horario y qué pasa fuera de ese horario',
          'Dirección y cómo llegar',
          'El canal con el que ya piden hora',
          'Qué llevar a la primera visita, si la clínica lo define',
        ],
      },
      {
        heading: 'Tono y límites clínicos',
        paragraphs: [
          'Hablamos de usted. No escribimos que es la mejor clínica, no inventamos casos y no publicamos fotos de antes y después salvo que sean del propio equipo y con autorización de la persona. No prometemos que un tratamiento va a resultar.',
        ],
        items: [
          'Nada de diagnósticos por internet',
          'Nada de precios de tratamientos que la clínica no haya entregado',
          'Nada de convenios que no estén vigentes por escrito',
        ],
      },
      {
        heading: 'Qué entra en la landing',
        paragraphs: [
          'Alcanzan cinco bloques: qué se atiende, nombres reales del equipo, cómo pedir hora, ubicación y preguntas que escribe la clínica. El video y el WhatsApp, si van, usan el número de la clínica y el paquete que los incluye.',
        ],
      },
    ],
    related: {
      slug: 'optica',
      reason: 'Si el local es de salud visual y no un box dental, el criterio está en la página de ópticas.',
    },
  },
  {
    slug: 'optica',
    label: 'Óptica',
    title: 'Landing para una óptica',
    description:
      'Sitio de una óptica: receta, marcos y horario, sin convenios ni promociones inventadas.',
    intro:
      'Quien busca una óptica quiere saber si puede sacar hora para receta, si el marco se elige en el local y a qué hora cierra el taller. Eso va antes que cualquier frase de marca.',
    blocks: [
      {
        heading: 'Examen, venta y taller no son lo mismo',
        paragraphs: [
          'Conviene separar el examen visual, la venta de cristales y la reparación. Si usted no hace examen, el sitio lo dice con la misma claridad que si lo hace. No mezclamos la óptica con una clínica ni con una tienda de moda.',
        ],
      },
      {
        heading: 'Precios, convenios y marcas',
        paragraphs: [
          'No publicamos un «desde» inventado ni un convenio con una isapre que usted no tenga por escrito. Si el precio depende de la receta, se dice así. Las marcas entran solo con la lista que usted entrega: no copiamos catálogos ajenos.',
        ],
        items: [
          'Horario de tienda y horario de taller, si son distintos',
          'Cómo retirar un trabajo ya encargado',
          'Estacionamiento o referencia solo si es cierto',
        ],
      },
      {
        heading: 'La visita manda',
        paragraphs: [
          'Dirección, horario y un canal para preguntar por una receta ya hecha resuelven más que un blog de tendencias. El tono es de usted. No hay reseñas fabricadas ni un ranking propio.',
        ],
      },
    ],
    related: {
      slug: 'clinica-dental',
      reason: 'Un box dental se escribe con otro límite: no mezclamos el examen de vista con una clínica.',
    },
  },
  {
    slug: 'abogados',
    label: 'Estudio de abogados',
    title: 'Landing para un estudio de abogados',
    description:
      'Página sobria para un estudio jurídico: materias reales y contacto, sin prometer el resultado de un juicio.',
    intro:
      'Quien busca un abogado quiere saber si el estudio toma su materia y cómo es el primer contacto. No quiere una promesa de ganar el juicio ni una balanza de adorno.',
    blocks: [
      {
        heading: 'Solo las materias que el estudio lleva',
        paragraphs: [
          'Familia, laboral, civil, sociedades u otras: se listan las áreas en las que de verdad trabajan. Una lista infinita parece un directorio. Si una materia no se toma, no se menciona.',
        ],
      },
      {
        heading: 'Identidad y primer mensaje',
        paragraphs: [
          'Van los nombres de quienes responden, la comuna del estudio y un correo o teléfono. No armamos un chat que «evalúa el caso» ni pedimos datos sensibles del juicio en un formulario abierto. El primer mensaje puede pedir el tipo de materia y la comuna, nada más.',
        ],
      },
      {
        heading: 'Lo que el texto no dice',
        paragraphs: [
          'No hay resultados garantizados, no hay cifras de dinero recuperado, no hay testimonios de clientes y no hay un cupo que se acaba hoy. Los honorarios se publican solo si el estudio los indicó. El tono es de usted.',
        ],
      },
    ],
    related: {
      slug: 'estudio-contable',
      reason: 'Los trámites tributarios no se explican como la página de un estudio jurídico.',
    },
  },
  {
    slug: 'estudio-contable',
    label: 'Estudio contable',
    title: 'Landing para un estudio contable',
    description:
      'Servicios contables, documentos de la primera reunión y límites, sin prometer ahorro de impuestos.',
    intro:
      'Un estudio contable se elige por claridad: qué trámites hace, si atiende a personas, a pymes o a ambas, y qué hay que juntar antes de la primera reunión.',
    blocks: [
      {
        heading: 'Trámites con nombre',
        paragraphs: [
          'Inicio de actividades, IVA mensual, renta anual, remuneraciones, término de giro. Cada uno en una frase que diga qué hace el estudio y qué no hace. Si no representa en un trámite ante el SII, no lo insinuamos.',
        ],
      },
      {
        heading: 'Documentos y fechas',
        paragraphs: [
          'Una lista corta de antecedentes —RUT de la empresa, último formulario que usted indique, no la clave— ahorra correos. Un calendario de fechas típicas es solo orientación: no es asesoría y no reemplaza una instrucción del SII.',
        ],
      },
      {
        heading: 'Lo que no prometemos',
        paragraphs: [
          'No prometemos devolución de impuestos ni «pagar menos». No usamos el logo del SII como si hubiera una afiliación. El formulario no pide claves. El tono es de usted.',
        ],
      },
    ],
    related: {
      slug: 'abogados',
      reason: 'Si el encargo es defensa o contratos, corresponde la página del estudio de abogados.',
    },
  },
  {
    slug: 'peluqueria',
    label: 'Peluquería',
    title: 'Landing para una peluquería',
    description: 'Servicios, duración y reserva de una peluquería, sin reseñas ni fotos ajenas.',
    intro:
      'Tu clientela ya te ve en redes. La landing existe para lo que el perfil no sostiene: dirección, horario de la semana, duración del servicio y cómo reservar sin escribir tres veces.',
    blocks: [
      {
        heading: 'La carta, con duración',
        paragraphs: [
          'Corte, color, brushing y tratamientos entran con el precio que tú diste. Si el valor cambia según el largo del pelo, se dice eso y no un número redondo falso. La duración estimada le sirve a quien pide hora en el almuerzo.',
        ],
      },
      {
        heading: 'Cómo se reserva de verdad',
        paragraphs: [
          'El botón usa tu agenda o el WhatsApp del salón, y solo en el paquete que lo incluye. Mientras no esté ese número, no ponemos un botón que abre un chat vacío. También va si atiendes con hora, por orden de llegada o ambos.',
        ],
      },
      {
        heading: 'Fotos del salón, no de otro',
        paragraphs: [
          'Solo fotos que tú nos entregues y que puedas usar. No bajamos imágenes de otros perfiles. No inventamos reseñas ni estrellas. Si no hay opiniones que se puedan citar, la página no lleva esa sección.',
        ],
      },
    ],
    related: {
      slug: 'centro-estetica',
      reason: 'Si el local es de cabina y no solo de pelo, el criterio está en el centro de estética.',
    },
  },
  {
    slug: 'centro-estetica',
    label: 'Centro de estética',
    title: 'Landing para un centro de estética',
    description: 'Tratamientos explicados en simple, sin claims médicos ni fotos de otros cuerpos.',
    intro:
      'El sitio tiene que explicar qué se hace en la cabina y qué no es un procedimiento médico. La persona llega con una expectativa; el texto la baja a algo concreto.',
    blocks: [
      {
        heading: 'Cada tratamiento en una ficha corta',
        paragraphs: [
          'Depilación, limpieza, cejas, uñas o aparatología, si existe en tu centro. Qué es, cuánto dura la sesión y si hay molestia: solo con la descripción que tú validas. Las contraindicaciones las escribe el profesional del local, no las improvisamos.',
        ],
      },
      {
        heading: 'Frases que no vamos a usar',
        paragraphs: [
          'No hay «eliminar grasa», «rejuvenecer años» ni resultados en una sesión. No llamamos clínica al centro si tú no lo declaraste con un profesional de la salud a cargo. No usamos fotos de bancos de imágenes.',
        ],
      },
      {
        heading: 'La primera visita',
        paragraphs: [
          'Si trabajas con evaluación previa, se dice: la primera visita no es el tratamiento. Precios solo los tuyos. Dirección, duración y canal de reserva. El tono es de tú, sin presión ni diminutivos.',
        ],
      },
    ],
    related: {
      slug: 'spa',
      reason: 'Un spa se organiza por la duración de la sesión, no por la carta de una cabina de estética.',
    },
  },
  {
    slug: 'spa',
    label: 'Spa y masajes',
    title: 'Landing para un spa',
    description: 'Duración, precio y dirección de un spa, sin adjetivos que esconden el dato.',
    intro:
      'En un spa la calma importa, pero quien reserva quiere un dato: cuánto dura el masaje, cuánto sale y si el lugar le queda cerca. Una página bonita que esconde el precio no reserva.',
    blocks: [
      {
        heading: 'La carta en minutos',
        paragraphs: [
          'Masaje, circuito o sesión en pareja: nombre, duración y qué incluye de verdad (camarín, ducha, infusión). Si no está incluido, no se escribe. Sacamos frases como «experiencia única» porque no dicen nada.',
        ],
      },
      {
        heading: 'Packs y regalos solo si existen',
        paragraphs: [
          'Un gift card entra si tú lo vendes y podemos explicar cómo se paga y cómo se canjea. Si no existe, no dibujamos uno. Los packs usan tus precios. No inventamos un descuento para apurar la reserva.',
        ],
      },
      {
        heading: 'Llegada',
        paragraphs: [
          'Dirección, horario, edad mínima si la tienes y qué pasa si la persona llega tarde. No prometemos el último cupo del día. Las fotos son del lugar, tuyas. El tono es de tú y sobrio.',
        ],
      },
    ],
    related: {
      slug: 'centro-estetica',
      reason: 'Si vendes tratamientos de cabina y no sesiones de spa, usa el criterio del centro de estética.',
    },
  },
  {
    slug: 'gimnasio',
    label: 'Gimnasio boutique',
    title: 'Landing para un gimnasio boutique',
    description: 'Planes, horario y clase de prueba, sin prometer una transformación física.',
    intro:
      'Un gimnasio chico no compite con una cadena mostrando torsos. Compite mostrando cupo, horario, qué incluye la mensualidad y cómo se prueba una clase.',
    blocks: [
      {
        heading: 'Planes que cobras hoy',
        paragraphs: [
          'Mensual, trimestral o clase suelta. El precio es el vigente. Si hay matrícula aparte, va en la misma tabla. No inventamos un plan de inauguración ni un convenio con un edificio que no esté firmado.',
        ],
      },
      {
        heading: 'La sala, no el eslogan',
        paragraphs: [
          'Aforo, tipos de clase y si hace falta experiencia previa. Los nombres de quienes dirigen la clase van si tú los das. No prometemos baja de peso ni un cambio de cuerpo en un plazo. Eso no es un dato.',
        ],
      },
      {
        heading: 'Cómo se entra a probar',
        paragraphs: [
          'Si hay clase de prueba, se explica cómo agendarla, qué llevar y dónde queda la sala. Si no hay prueba gratis, no la anunciamos. El horario semanal importa más que una frase motivacional.',
        ],
      },
    ],
    related: {
      slug: 'spa',
      reason: 'El spa vende sesiones sueltas; el gimnasio vende planes. No sirve el mismo texto.',
    },
  },
  {
    slug: 'cafeteria',
    label: 'Cafetería',
    title: 'Landing para una cafetería',
    description: 'Carta, horario y dirección de una cafetería, sin un menú de plantilla.',
    intro:
      'La landing de una cafetería es la carta y la puerta: qué sirves, a qué hora abres y cómo llegar caminando. Lo demás puede esperar.',
    blocks: [
      {
        heading: 'La carta que está hoy',
        paragraphs: [
          'Café, té, pastelería o sándwich, y las opciones sin lactosa solo si las tienes. Publicamos la carta que tú nos pasas. No dejamos una plantilla de productos que no están. Si un ítem depende del día, se puede decir.',
        ],
      },
      {
        heading: 'Horario y permanencia',
        paragraphs: [
          'Semana y fin de semana, si te cierras distinto. Si cierras por vacaciones, no dejamos el horario anterior. Wi-Fi o enchufes se mencionan solo si son ciertos: hay quien elige el local por eso.',
        ],
      },
      {
        heading: 'Barra, no tienda en línea',
        paragraphs: [
          'Si atiendes solo en el local, el sitio no promete despacho. Si hay despacho, van la zona y el mínimo que tú definas. No armamos un catálogo de cientos de productos: eso no es esta landing. El tono es el del mesón.',
        ],
      },
    ],
    related: {
      slug: 'restaurante',
      reason: 'Si hay cocina de almuerzo o cena y no solo barra, mira el criterio del restaurante.',
    },
  },
  {
    slug: 'restaurante',
    label: 'Restaurante de barrio',
    title: 'Landing para un restaurante de barrio',
    description:
      'Menú, reserva y horario de cocina, sin ranking inventado ni platos de otro local.',
    intro:
      'Un restaurante de barrio necesita que se entienda la cocina, a qué hora cierra la cocina (no solo la puerta) y si hay que reservar. No necesita decir que es el mejor de la comuna.',
    blocks: [
      {
        heading: 'Menú y restricciones',
        paragraphs: [
          'Entradas, fondo y postre, o el menú del día si ese es tu formato. Vegetariano, sin gluten u otras marcas se publican solo cuando la cocina las confirma. No etiquetamos un plato por nuestra cuenta.',
        ],
      },
      {
        heading: 'Reserva y puerta',
        paragraphs: [
          'Si tomas reserva, el botón usa tu canal. Si no tomas, se dice para que nadie llegue con una mesa asegurada. El horario de cocina puede cerrar antes que el salón: eso va escrito. Estacionamiento solo si existe.',
        ],
      },
      {
        heading: 'Fotos de tus platos',
        paragraphs: [
          'Fotos que tú sacaste o que nos autorizaste. No usamos comida genérica de un banco de imágenes: no es tu plato. No hay estrellas ni una nota puesta por nosotros. Una reseña, si algún día se cita, lleva fuente y tu permiso.',
        ],
      },
    ],
    related: {
      slug: 'cafeteria',
      reason: 'Si el local es de barra y pastelería, el criterio de la cafetería es otro.',
    },
  },
  {
    slug: 'taller-mecanico',
    label: 'Taller mecánico',
    title: 'Landing para un taller mecánico',
    description: 'Qué autos recibe el taller, cómo se cotiza y dónde dejarlo, sin garantías inventadas.',
    intro:
      'Quien busca un taller quiere saber si recibes su auto, cómo se pide una revisión y dónde dejarlo. «Mecánica integral» no responde ninguna de las tres.',
    blocks: [
      {
        heading: 'Qué entra y qué no',
        paragraphs: [
          'Tipos de vehículo que sí tomas y los que no, si tienes ese límite: diesel, cajas automáticas, motos. Servicios con nombre —frenos, distribución, diagnóstico, revisión de viaje— y no trabajos que derivas sin decirlo.',
        ],
      },
      {
        heading: 'La cotización no es la landing',
        paragraphs: [
          'Explicamos que el valor sale después de ver el auto, qué datos pides (año, síntoma, patente si tú la pides) y en qué horario se puede dejar. No inventamos una garantía de kilómetros ni un precio de entrada para un embrague.',
        ],
      },
      {
        heading: 'El patio',
        paragraphs: [
          'Dirección, si hay sala de espera y cómo se paga. El WhatsApp, si va, es el del taller y solo con tu número. El tono es directo. No hace falta jerga para parecer más grandes.',
        ],
      },
    ],
    related: {
      slug: 'ferreteria',
      reason: 'Vender materiales no es recibir un auto. La ferretería tiene otra página.',
    },
  },
  {
    slug: 'inmobiliaria',
    label: 'Inmobiliaria local',
    title: 'Landing para una inmobiliaria local',
    description:
      'Comunas reales y fichas propias de una corredora, sin copiar portales ni prometer plusvalía.',
    intro:
      'Una corredora local no necesita parecer un portal nacional. Necesita decir en qué comunas trabaja, quién responde y cómo se publica una propiedad que sí está en cartera.',
    blocks: [
      {
        heading: 'El territorio, sin repetir comunas',
        paragraphs: [
          'Se nombran las comunas donde de verdad tomas encargos. No armamos una página por comuna ni un párrafo repetido con el barrio cambiado. Si son varias sucursales, eso es multi sede y se cotiza aparte: no entra en el precio de una landing.',
        ],
      },
      {
        heading: 'Fichas que son tuyas',
        paragraphs: [
          'Cada propiedad lleva datos que tú entregas: venta o arriendo, comuna, dormitorios y precio si quieres mostrarlo. No copiamos avisos de portales ni fotos de otros corredores. Si no hay propiedades cargadas, no mostramos departamentos de ejemplo.',
        ],
      },
      {
        heading: 'Sin rentabilidad prometida',
        paragraphs: [
          'No escribimos plusvalía, «se arrienda en una semana» ni un retorno. El formulario pide tipo de operación y comuna, no documentos de identidad. El nombre de quien responde va visible. El tono es concreto.',
        ],
      },
    ],
    related: {
      slug: 'abogados',
      reason: 'La compraventa no se explica como la página de un estudio jurídico.',
    },
  },
  {
    slug: 'veterinaria',
    label: 'Veterinaria',
    title: 'Landing para una veterinaria',
    description: 'Especies, urgencia y horario de una veterinaria, sin consejos médicos improvisados.',
    intro:
      'Quien busca una veterinaria suele estar apurado. La página tiene que decir si atiendes esa especie, si hay urgencia y a qué hora cierran.',
    blocks: [
      {
        heading: 'Especie y urgencia, en la primera pantalla',
        paragraphs: [
          'Perros, gatos u otros: solo los que atiendes. Si no hay urgencia de noche, se dice y, si tú indicas un lugar de derivación, se nombra ese lugar. No inventamos un turno. No damos dosis ni diagnósticos en el texto.',
        ],
      },
      {
        heading: 'Servicios del box',
        paragraphs: [
          'Consulta, vacunas, peluquería o cirugía solo si existen en tu local. El precio de la consulta, si se publica, es el tuyo. El calendario de vacunas es el que usa tu médico veterinario, no uno armado por nosotros.',
        ],
      },
      {
        heading: 'Cómo llegar con el animal',
        paragraphs: [
          'Dirección, si se atiende con hora y qué hacer si no puede esperar. El teléfono se ve sin buscar. No usamos fotos de mascotas de banco. El tono es claro, sin tratar al tutor como si fuera un niño.',
        ],
      },
    ],
  },
  {
    slug: 'escuela-idiomas',
    label: 'Escuela de idiomas',
    title: 'Landing para una escuela de idiomas',
    description: 'Niveles, modalidad y horario de una escuela, sin prometer fluidez en un plazo.',
    intro:
      'Una escuela se elige por el nivel, el horario y si la clase es presencial. No por un lema de fluidez en treinta días, que no vamos a escribir.',
    blocks: [
      {
        heading: 'Idioma, nivel y sala',
        paragraphs: [
          'Los idiomas que dictas, los niveles que usas y si la clase es en la sede. Si no hay modalidad en línea, no la sugerimos. El cupo por sala solo si tú lo fijas. Quienes enseñan se nombran si nos das el nombre y el idioma.',
        ],
      },
      {
        heading: 'Cómo entra un alumno',
        paragraphs: [
          'Prueba de nivel: cuánto dura, si tiene costo y cuándo parte el curso. Esas fechas cambian cada semestre y se publican cuando tú las confirmas. No dejamos el calendario del año pasado. El precio es el vigente.',
        ],
      },
      {
        heading: 'Sin método secreto',
        paragraphs: [
          'No hay fluidez garantizada ni testimonios de alumnos inventados. Si un alumno acepta contar su experiencia con nombre, se cita; si no, esa sección no existe. El tono es el de la secretaría.',
        ],
      },
    ],
  },
  {
    slug: 'ferreteria',
    label: 'Ferretería',
    title: 'Landing para una ferretería',
    description: 'Rubros, horario y cotización de una ferretería, sin un catálogo falso.',
    intro:
      'Una ferretería de barrio no cabe en un catálogo de miles de códigos. La landing dice qué rubros trabajas, si despachas y cómo se cotiza una lista de materiales.',
    blocks: [
      {
        heading: 'Lo que hay en la sala',
        paragraphs: [
          'Construcción, gasfitería, electricidad, pintura o jardín: los rubros que de verdad tienes. No listamos marcas que no vendes ni copiamos el árbol de una cadena. Si eres fuerte en un rubro, ese va primero.',
        ],
      },
      {
        heading: 'Cotizar y despachar',
        paragraphs: [
          'Cómo se manda una lista, en qué horario responden y si hay despacho, retiro o ambos. La zona de despacho es la que tú cubres. No escribimos «todo Santiago» por defecto ni un despacho gratis que no exista.',
        ],
      },
      {
        heading: 'Esto no es una tienda con carro',
        paragraphs: [
          'Un ecommerce con inventario en vivo queda fuera de la landing. El sitio muestra el oficio, el horario, la dirección y el canal de cotización. Precios de productos solo con una lista corta y vigente que tú nos pases. El tono es práctico.',
        ],
      },
    ],
    related: {
      slug: 'taller-mecanico',
      reason: 'Si el negocio recibe vehículos y no vende materiales, corresponde la página del taller.',
    },
  },
];

export function findRubro(slug: string): Rubro | undefined {
  return rubros.find((item) => item.slug === slug);
}
