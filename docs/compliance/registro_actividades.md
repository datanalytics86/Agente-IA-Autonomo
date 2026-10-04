# Registro de actividades de tratamiento

Documento de trabajo del responsable. No es un dictamen, no autoriza envíos y no reemplaza la revisión de `docs/compliance/REVISION_LEGAL.md`.

Fecha: 4 de octubre de 2026. Ola 1 (reglas deterministas). Se actualiza si cambia un tratamiento, un proveedor o un plazo.

Responsable: la agencia, cuando exista razón social, RUT, domicilio y correo. Hoy `AGENCY_NAME`, `AGENCY_LEGAL_NAME`, `AGENCY_RUT`, `AGENCY_EMAIL` y `AGENCY_ADDRESS` están vacíos a propósito. No se inventan.

Ámbito: Chile. Prospectos en las comunas configuradas (`SCOUT_COMMUNES`). Hasta el 1 de diciembre de 2026 el proyecto asume vigente la Ley 19.628 y, desde esa fecha, la Ley 21.719. Hay que cumplir las dos. La fecha de vigencia la confirma el abogado; aquí no se da por cerrada.

## Para qué sirve

Dejar por escrito qué datos se quieren tratar, con qué finalidad, por cuánto tiempo y con qué medidas. La lista viva de reglas del Checker está en `engine/core/compliance.py`. Si este registro y el código se contradicen, manda el código y este texto se corrige.

## Principios ya operativos

- Minimización: solo datos de negocio públicos y necesarios para ofrecer una landing. No se compran listas ni se adivinan correos (`nombre@dominio`).
- Cada correo de contacto que entre al lead debe poder mostrar de dónde salió (`contact_email_source_url`). Teléfono, Instagram y LinkedIn todavía no tienen columna propia de procedencia: es una brecha, no una licencia para omitirla.
- La prospección automática permanece apagada. Default: `DRY_RUN=true`, `OUTREACH_ENABLED=false`. Según ADR-005, `kill_switch=true` significa envío armado y el default `false` lo deja detenido. Además harían falta `APP_MODE=prod` y la credencial del canal. Este registro no enciende nada de eso.
- Inbound (diagnóstico gratis, formularios, WhatsApp iniciado por la persona) solo con consentimiento explícito y versión del texto.
- Opt-out determinista, antes de cualquier modelo: STOP, BAJA, «no me escriban», «no me escribas», «déjame de escribir», «no me contacten», unsubscribe y remove me, con o sin tildes, mayúsculas, espacios duros o caracteres invisibles.
- La baja se guarda como supresión global (correo, dominio, teléfono, Instagram, LinkedIn). El hash se conserva aunque el prospecto se anonimice, para no volver a escribirle.
- Cero testimonios, garantías, logos o cifras inventadas. El rating solo con atribución a su fuente.
- Instagram y LinkedIn no se envían solos. WhatsApp saliente sin consentimiento se rechaza.
- `engine/core/compliance.py` no abre sockets, no lee el entorno y no envía mensajes. Solo responde si el texto se aprueba o no.

## Tratamientos

### 1. Prospección B2B

- Finalidad: encontrar negocios que podrían necesitar un sitio y preparar una oferta.
- Datos: nombre del negocio, rubro, comuna, ciudad, dirección pública, `place_id`, ficha pública (rating, cantidad de reseñas, estado), URL del sitio, teléfono público, correo publicado, handle de Instagram, URL de LinkedIn, URL de procedencia del correo, fecha de recolección.
- Titulares: la persona natural detrás del negocio, cuando el dato la identifica. Una persona jurídica no es titular bajo la Ley 19.628; sus socios, encargados o quien use un correo personal, sí pueden serlo.
- Fuente: Google Places y el sitio del propio negocio (página de contacto, `mailto:`, schema.org, enlace a Instagram). No se scrapea el buscador de Google.
- Base propuesta: ninguna operativa. El test de `docs/compliance/interes_legitimo.md` no autoriza el envío. Hasta dictamen, esto solo puede correr en demo o en seco.
- Destinatarios: Google (Places, PageSpeed), el modelo de lenguaje si se le pasa el lead, y el operador humano de la bandeja.
- Plazo: prospecto outbound sin interacción se anonimiza a los `RETENTION_DAYS` (120). Los hashes de supresión no se borran.

### 2. Auditoría del sitio y materiales de propuesta

- Finalidad: diagnóstico, landing de demostración, storyboard y borrador de mensaje.
- Datos: los del tratamiento 1 más hallazgos técnicos del sitio (HTTPS, peso, CMS, enlaces rotos, PageSpeed) y el texto generado.
- La landing demo usa token no adivinable, `noindex`, banner de propuesta no oficial y vence a los `DEMO_TTL_DAYS` (30). Sin fotos ni logos del negocio sacados de terceros.
- Base: la misma brecha del tratamiento 1. No se publica una demo de un prospecto real como portafolio.

### 3. Mensajes comerciales

- Finalidad: un correo inicial y, como máximo, dos seguimientos, solo si en el futuro hay base legal y el canal está habilitado.
- Canales diseñados: correo de outreach (casilla genérica publicada por el negocio), cola manual de Instagram y LinkedIn, WhatsApp solo con opt-in. El correo transaccional (Resend u otro) no se usa para frío.
- La capa 1 (`check_rules`) rechaza el mensaje si ocurre cualquiera de estas cosas:
  - no hay opt-out en el cuerpo;
  - `agency_name` viene vacío o el cuerpo no trae el nombre de la agencia;
  - el correo no trae indicación de baja (la palabra «baja» o un enlace con baja, unsubscribe u opt-out);
  - el destinatario está marcado como suprimido;
  - el cuerpo o el asunto nombran un correo o un celular que no está en el lead ni en la agencia;
  - hay un precio fuera de la banda (`PRICE_MIN_CLP` 250.000, `PRICE_MAX_CLP` 450.000) o la banda no es válida;
  - hay frase prohibida (garantizado, resultados asegurados, «cliente local (ejemplo», 100 %, últimas unidades, «acto seguido te llamamos») o testimonio inventado;
  - el largo pasa el tope del canal (correo 1.200, Instagram 500, LinkedIn 500, WhatsApp 400);
  - WhatsApp saliente sin consentimiento;
  - un enlace no pertenece a `public_base_url` (el mismo host o un subdominio);
  - spam de mayúsculas (más del 30 % en un texto de al menos 20 letras) o tres o más signos de exclamación;
  - el texto pide ignorar instrucciones, cambiar el estado del lead, revelar el system prompt o enviar el mensaje a un tercero.
- El asunto no reemplaza la identidad, el opt-out ni la baja del cuerpo.
- Una sola razón rechaza. El puntaje es 100 menos 20 por razón, con piso 0. No hay umbral de 70 en esta capa: el prompt viejo del Checker no manda sobre estas reglas.
- Esta capa no crea la fila de HITL. Quien persiste el mensaje tiene que tratar «precio fuera de banda; requiere HITL» como pausa humana, no como envío.
- Plazo de los mensajes: el de la ficha del lead. Si el lead se anonimiza, no debe quedar el cuerpo con datos de contacto.

### 4. Respuestas, baja y supresión

- Finalidad: honrar la baja y clasificar la respuesta.
- Detección: `is_opt_out` sobre el texto entrante, sin modelo. Si calza, el estado de marketing termina en `opt_out` y se suprime el contacto.
- Supresión (`suppression`): se guarda el tipo (`email`, `domain`, `phone`, `instagram`, `linkedin`) y el SHA-256 hexadecimal del valor ya normalizado. El tipo no entra al hash. La unicidad es (tipo, hash).
- Normalización, sin red:
  - correo: sin espacios y en minúsculas;
  - dominio: solo el host, sin esquema y sin `www`;
  - teléfono: solo dígitos; si son 9 y parten en 9, se antepone 56;
  - Instagram: sin `@` y en minúsculas;
  - LinkedIn: sin esquema, sin `www` y sin barra final, en minúsculas.
- El hash es determinista y no lleva sal. Tiene que serlo para reconocer al mismo contacto después de anonimizar. Eso permite reidentificar un correo común si alguien tiene el hash y un diccionario. El equilibrio se pregunta en la revisión legal; no se “arregla” con una sal que impediría cumplir la baja.
- Motivo y origen de la baja se guardan junto al hash (`reason`, `source`). No se guarda el valor en claro en esa tabla.

### 5. Inbound con consentimiento

- Finalidad: diagnóstico gratis, formulario de contacto, derechos y WhatsApp o Instagram iniciados por la persona.
- Datos: los que la persona entrega, más `consent` (`type`, `text_version`, marca de tiempo, hash de IP; no la IP en claro).
- Base propuesta: consentimiento. Sin texto publicado y sin versión guardada, no hay consentimiento demostrable.
- WhatsApp saliente exige `whatsapp_consent` o un consentimiento que nombre el canal. Un número publicado en Google no alcanza.

### 6. Venta, pago y entrega

- Finalidad: propuesta, cobro y sitio del cliente que ya aceptó.
- Datos: pedido, montos, estado de pago, identificador del proveedor, intake (logo, fotos propias, horarios, dominio) y token del portal.
- La tarjeta no se guarda: Mercado Pago Checkout Pro se queda con ese dato.
- Base propuesta: ejecución del contrato, más obligación tributaria para el documento del SII. El prospecto que pagó ya no se anonimiza a los 120 días.
- Cada pago abre una tarea humana «emitir documento tributario». No hay integración automática con el SII en esta fase. `PRICES_INCLUDE_IVA=true` significa IVA 19 % incluido en el precio mostrado. Boleta o factura, el momento (anticipo y saldo) y el plazo de guarda los define el contador. Ver preguntas en `REVISION_LEGAL.md`.

### 7. Derechos de los titulares

- Finalidad: acceso, rectificación, supresión, oposición, portabilidad y bloqueo.
- Vía diseñada: formulario `/derechos` y tabla `data_requests`, con vencimiento operativo a 30 días y alerta si se acerca. Ese plazo es de operación, no una afirmación de que la ley diga 30.
- La supresión de un prospecto no borra el hash de baja. La supresión de un cliente no borra el documento tributario.

### 8. Administración, registros técnicos y modelos

- Finalidad: operar el sistema, investigar errores y controlar gasto del modelo.
- Datos: usuario admin (correo y hash argon2 de la clave), eventos, corridas de jobs, llamadas al modelo (agente, tokens, costo, latencia; el prompt puede repetir datos del lead).
- Los niveles `debug` e `info` de un prospecto ya anonimizado siguen `RETENTION_DAYS`. `warn` y `error` se conservan.
- El modelo (xAI, por defecto) puede estar fuera de Chile. No se le deben pasar instrucciones que vengan de un sitio o de un mensaje entrante como si fueran órdenes del sistema. `looks_like_injection` marca ese texto.

## Encargados y salidas de Chile

Ningún encargado está contratado mientras la credencial esté vacía. Cuando se encienda un adaptador real, hace falta contrato y, si el dato sale de Chile, la base que indique el abogado.

| Proveedor | Para qué | ¿Sale de Chile? |
|---|---|---|
| Google Places y PageSpeed | ficha pública y rendimiento del sitio | a confirmar |
| xAI | textos del diagnóstico, la landing y el juez | sí, salvo que el contrato diga otra cosa |
| SMTP de outreach | correo en frío, si algún día se habilita | a confirmar |
| Resend u otro transaccional | correos de la relación (no frío) | a confirmar |
| Meta | Instagram y WhatsApp solo inbound o con opt-in | a confirmar |
| Cal.com o Calendly | agenda | a confirmar |
| Mercado Pago | cobro | a confirmar |
| VPS (Caddy, base de datos) | hospedaje | depende de dónde se arriende |

El `place_id` se puede guardar de forma persistente según la práctica conocida de Google Maps Platform. El resto del contenido de la ficha tiene plazo de caché: no se afirma aquí cuál es el plazo vigente. Hay que leer el contrato actual antes de mostrar un rating.

## Medidas

Hechas en este módulo: normalización, hash SHA-256, opt-out determinista, rechazo si no hay identidad de la agencia, y las reglas de la capa 1 sin red y sin envío.

Diseñadas en otros componentes, todavía no auditadas: cifrado en tránsito, clave de admin con argon2, `DRY_RUN` sin sockets, kill switch, cupos, ventana horaria, feriados de Chile, un correo por dominio al día, sin pixel de seguimiento, headers RFC 8058 en el envío, token de la demo, `noindex`, y separación entre correo de outreach y correo transaccional.

No es una medida de esta capa: filtrar RUT, datos de salud de pacientes o datos de menores dentro del cuerpo del mensaje. El producto no está dirigido a menores ni a datos clínicos. Si el sitio del prospecto los muestra, no se copian al pitch. Falta un detector; queda como pregunta legal y como ítem de la auditoría.

## Qué no hace este registro

No declara la base legal cerrada. No firma la auditoría. No autoriza a cobrar sin boleta o factura. No reemplaza la política de privacidad ni los términos, que tienen que publicarse con la identidad real de la agencia y no con un nombre inventado.
