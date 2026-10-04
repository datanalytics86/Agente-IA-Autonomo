# Preguntas para revisión legal

Esto no es un dictamen. No habilita el outreach, no interpreta la ley en nombre de la agencia y no reemplaza a un abogado con inscripción vigente en Chile. Las respuestas tienen que venir por escrito, con la identidad real de la agencia (razón social, RUT, domicilio, correo). Hoy esos datos están vacíos a propósito.

Fecha del borrador: 4 de octubre de 2026.

Supuesto del proyecto, que hay que confirmar y no dar por sentado: la Ley 21.719 entra en vigencia el 1 de diciembre de 2026 y hasta entonces se aplica la Ley 19.628. El diseño intenta cumplir las dos. El test de ponderación está en `docs/compliance/interes_legitimo.md` y su conclusión actual es no enviar. El registro de tratamientos está en `docs/compliance/registro_actividades.md`.

Mientras no haya respuesta, se mantiene la opción más restrictiva: `OUTREACH_ENABLED=false`, `DRY_RUN=true`, sin cobro real y sin textos legales publicados con un nombre inventado.

## Ley 21.719

1. ¿Cuál es la fecha exacta de vigencia y qué artículos de la Ley 19.628 siguen aplicando durante la transición y después?
2. ¿La prospección B2B a una persona natural con giro, una EIRL o quien atiende el correo de un local puede apoyarse en interés legítimo, o exige consentimiento?
3. ¿El correo `info@` o `contacto@` publicado por el negocio en su propio sitio es dato personal cuando identifica a una persona natural? ¿Y el teléfono celular publicado en la ficha de Google?
4. ¿Qué artículo regula la oposición a la prospección comercial, y exige que la baja sea tan fácil como el contacto inicial?
5. ¿Hace falta evaluación de impacto para este volumen (hasta unas decenas de prospectos al día, un VPS, modelos y correo fuera de Chile)?
6. ¿Hace falta delegado de protección de datos para una agencia de un solo administrador?
7. ¿Qué debe contener el registro de actividades y hay que inscribir o comunicar algo ante la Agencia de Protección de Datos Personales?
8. Transferencias o encargos: xAI (el prompt puede incluir datos del lead), Google Places y PageSpeed, SMTP de outreach, Resend u otro transaccional, Mercado Pago, Meta, Cal.com o Calendly, y el VPS. ¿Cuáles son transferencia internacional y qué mecanismo exige la ley?
9. El hash de supresión es SHA-256 sin sal, a propósito, para reconocer al mismo contacto después de anonimizar. ¿Eso cumple el deber de seguridad, o hay una forma de seudonimizar que igual permita la baja?
10. El sistema vence las solicitudes de derechos a los 30 días. ¿Es el plazo legal para acceso, rectificación, supresión, oposición, portabilidad y bloqueo, o hay plazos distintos por derecho?
11. ¿La anonimización a los 120 días de un prospecto outbound sin interacción equivale a supresión o a disociación? ¿Pueden quedar `place_id`, comuna y los hashes?
12. Si el interés legítimo llegara a ser viable, ¿cubre los dos seguimientos o solo el primer correo?
13. La landing demo muestra el nombre del negocio bajo una URL con token, `noindex` y un banner de propuesta no oficial, y vence a los 30 días. ¿Eso es una comunicación de datos? ¿El banner basta?
14. El producto no está dirigido a menores ni a datos de pacientes. No hay un detector de RUT, datos de salud o datos de menores en el cuerpo del mensaje. ¿Hay que filtrar igual los rubros de salud, educación o actividad que pueda ser de un menor?
15. Teléfono, Instagram y LinkedIn no tienen columna propia de procedencia; el correo sí (`contact_email_source_url`). ¿Basta un campo por contacto o hace falta procedencia en cada dato?

## Ley 19.628

16. Hasta la vigencia de la Ley 21.719, ¿la regla sigue siendo la autorización del titular, y la prospección sin esa autorización está prohibida aunque el dato esté en el sitio del negocio?
17. ¿El sitio del propio negocio y la ficha de Google son fuentes accesibles al público para el correo y el teléfono? ¿Qué se puede hacer con ese dato y qué hay que informar, y cuándo?
18. ¿Hay que informar al titular al momento de registrar el dato, antes del primer correo, o basta con la identidad y la baja dentro del propio correo?
19. ¿Las personas jurídicas pueden quedar fuera del régimen, y cómo se distingue en la práctica un correo de empresa de un correo de persona natural sin preguntarle?

## Ley 19.496, artículo 28 B

20. ¿El artículo 28 B aplica cuando el destinatario es un correo de empresa y todavía no es consumidor de la agencia? ¿Y si el negocio es una persona natural?
21. ¿Basta el texto «responde BAJA» o hace falta una dirección (correo o URL) que funcione sin iniciar sesión? La capa 1 hoy acepta la palabra «baja» o un enlace cuyo destino contiene baja, unsubscribe u opt-out. ¿Eso cumple o hay que exigir siempre la URL?
22. ¿El mecanismo RFC 8058 (`List-Unsubscribe` y `List-Unsubscribe-Post: List-Unsubscribe=One-Click`), más la página `/baja`, cumple la «dirección válida»? ¿Quién debe aparecer como remitente: el nombre de fantasía, la razón social, o los dos?
23. Un STOP, «no me escriban» o «remove me» recibido por respuesta: ¿obliga a cortar solo el correo o todos los canales? El diseño corta todos, por supresión global. ¿Es obligatorio o solo prudente?
24. ¿El asunto tiene que indicar la materia del servicio, además del cuerpo? La capa 1 no deja que el asunto reemplace el opt-out ni la identidad del cuerpo.
25. ¿Dos seguimientos, sin nueva autorización y sin respuesta, caben en el artículo si el primero ya traía la vía de baja?

## Meta (Instagram y WhatsApp)

Hay que leer los términos vigentes (política de mensajería de Instagram y política de WhatsApp Business), no una paráfrasis de este archivo.

26. ¿Preparar un borrador y que una persona lo copie y lo envíe por Instagram es automatización prohibida, o es aceptable si el envío es manual y queda registro de quién lo marcó como enviado?
27. ¿La API de Instagram se puede usar solo para contestar una conversación iniciada por el usuario? ¿Qué texto de consentimiento hay que guardar y por cuánto tiempo?
28. WhatsApp: ¿qué prueba de opt-in hay que guardar (texto, versión, fecha, origen) para escribir fuera de la ventana de 24 horas? La capa 1 rechaza WhatsApp saliente si no hay `whatsapp_consent` o un consentimiento que nombre el canal.
29. ¿Un click-to-chat iniciado por el usuario alcanza como opt-in para los mensajes siguientes dentro de esas 24 horas?
30. ¿Está prohibido el primer contacto por WhatsApp aunque el número esté publicado en el sitio o en Google? El diseño lo trata como prohibido. Confirmar que no hay una excepción por “número público”.

## LinkedIn

31. ¿El envío manual de un mensaje copiado desde la cola interna infringe la prohibición de automatización o de scraping de LinkedIn?
32. ¿Se puede guardar la URL pública del perfil (`linkedin_url`) y por cuánto tiempo? ¿Hace falta atribución o un aviso al titular?

## Google Places

Hay que leer los términos vigentes de Google Maps Platform antes de guardar o mostrar una ficha.

33. ¿El `place_id` se puede almacenar de forma permanente y el resto (nombre, dirección, teléfono, rating, horarios, fotos) tiene un plazo de caché? ¿Cuál es ese plazo hoy?
34. ¿Mostrar el rating en la landing demo exige atribución visible a Google, y se puede mostrar si la ficha ya superó el plazo de caché?
35. ¿Está prohibido completar datos que Places no trajo usando resultados de búsqueda de Google, distinto de leer el sitio del propio negocio?
36. ¿El User-Agent identificable, el respeto de `robots.txt` y el tope de una solicitud por segundo al sitio del negocio alcanzan, o hace falta algo más para ese scraping acotado?

## Boleta del SII

La fase inicial no se conecta al SII. Al confirmarse un pago se crea una tarea humana «emitir documento tributario». `PRICES_INCLUDE_IVA=true` deja el IVA de 19 % incluido en el precio. No hay inicio de actividades cargado en el sistema.

37. Por cada pago de Mercado Pago, ¿corresponde boleta o factura electrónica, y en qué momento: al anticipo del 50 %, al saldo, o en ambos?
38. Si el precio ya incluye IVA, ¿cómo debe desglosarse en el documento para que no se cobre dos veces?
39. ¿Se puede ofrecer un cobro real de demostración sin documento, o hay que impedir cualquier pago de producción hasta el inicio de actividades y la razón social?
40. ¿La tarea humana de emitir el documento cumple en la fase inicial, o el SII exige emisión electrónica en el acto del pago?
41. ¿Cuántos años se guardan boletas, facturas y notas de crédito, y cómo se separa eso de la anonimización a 120 días? El cliente que pagó no es un prospecto sin interacción.
42. Si el pedido queda en `refunded`, ¿qué documento hay que emitir y quién lo dispara, el sistema o el contador?

## Cierre que se le pide al abogado

Marcar una sola opción y firmarla:

- (a) outreach apagado hasta un nuevo aviso;
- (b) franja permitida, con condiciones que el diseño actual pueda cumplir sin nuevas excepciones;
- (c) el modelo de prospección en frío no es viable.

Sin esa marca, el proyecto se queda en (a). Este archivo no es esa marca.
