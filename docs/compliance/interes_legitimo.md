# Test de ponderación — interés legítimo en prospección B2B

No es un dictamen. No es base para encender envíos. Si el abogado no lo confirma por escrito, el resultado de este test sigue en pie: el outreach automático queda apagado.

Fecha: 4 de octubre de 2026. Responsable: la agencia, todavía sin razón social ni RUT cargados. Hay que rehacer el test si cambian el volumen, la fuente de los datos, los canales o el país desde el que se trata.

## 1. Tratamiento que se evalúa

Enviar, a un negocio en Chile, un correo no pedido ofreciendo una landing (paquetes entre 250.000 y 450.000 CLP), con un diagnóstico breve y un enlace a una demo. Como máximo: un correo inicial y dos seguimientos. Se detiene si hay respuesta, rebote o baja.

Queda fuera de este test, y prohibido por las reglas aunque el interés legítimo existiera:

- WhatsApp en frío;
- mensajes automáticos de Instagram o LinkedIn;
- correos adivinados, listas compradas o sondeo SMTP;
- pixel de seguimiento;
- testimonios, garantías o precios fuera de la banda;
- cualquier mensaje sin identidad de la agencia y sin vía de baja.

Esos canales y esas prácticas no se “salvan” con este documento.

## 2. Interés del responsable

Ofrecer un servicio B2B a negocios que ya tienen actividad pública (ficha o sitio) y a los que una landing les podría servir. El interés es comercial y propio. No es una obligación legal, no es interés vital y no es una tarea pública.

El mismo fin se puede perseguir sin escribirle a nadie que no lo pidió: diagnóstico gratis con consentimiento, formulario de contacto y referidos. El correo en frío es una conveniencia, no la única vía.

## 3. Necesidad y minimización

Si se hiciera, el dato usado sería el estrictamente necesario para un solo contacto: nombre del negocio, comuna, un correo genérico publicado por el propio negocio en su sitio (`contacto@`, `info@` y equivalentes), la URL donde se vio ese correo, y un hecho comprobable del sitio. No hace falta el teléfono para el correo. No hace falta el rating si no se va a citar con atribución. No se necesita el contenido completo de la ficha de Google más allá del plazo que permitan sus términos.

Esa minimización está diseñada. No está demostrada en producción, porque el envío real no está habilitado.

## 4. Titulares e intereses en juego

El destinatario puede ser:

- una persona jurídica, que bajo la Ley 19.628 no invoca la protección de datos por sí misma;
- una persona natural con giro, una EIRL o quien atiende el correo del local;
- una persona natural cuyo correo personal (gmail, hotmail u otro) está publicado como contacto del negocio.

En los dos últimos casos hay un titular. Sus intereses son no ser contactado, que no usen su correo para una finalidad que no pidió, y poder cortar el contacto de una vez y para todos los canales. El daño de un solo correo es bajo. El diseño apunta a decenas de prospectos al día (`SCOUT_DAILY_LIMIT` 30, tope de outreach que puede subir hasta 50). A esa escala el efecto ya no es un recado aislado.

No hay relación previa. La persona no pidió la oferta. Publicar un correo en la página de contacto sirve para que los clientes del negocio escriban, no para que una agencia desconocida arme una secuencia.

## 5. Expectativa razonable

No está claro, en Chile y a esta fecha, que quien publica `info@` en su sitio espere prospección de un proveedor de sitios web. Menos claro es el caso del correo personal usado para el negocio. Mientras eso no esté resuelto, la expectativa razonable no se presume a favor de la agencia.

Tampoco ayuda el calendario. Al 4 de octubre de 2026 la ley vigente, según el supuesto del proyecto, sigue siendo la Ley 19.628, armada sobre la autorización del titular y no sobre el interés legítimo. La Ley 21.719, que sí contemplaría esa base, entraría el 1 de diciembre de 2026. Usar una base que todavía no rige, o que rige con requisitos que un abogado no revisó, es la opción menos segura.

## 6. Salvaguardas que el diseño ya tiene

Sirven para bajar el riesgo. No invierten la ponderación.

- Opt-out determinista (STOP, BAJA, «no me escriban», «no me escribas», «déjame de escribir», «no me contacten», unsubscribe, remove me), con y sin tildes ni mayúsculas.
- Supresión global e inmediata por hash, conservada después de anonimizar.
- Identidad de la agencia obligatoria en el cuerpo. Si `agency_name` viene vacío, la capa 1 no aprueba.
- En el correo, indicación de baja en el cuerpo. El header `List-Unsubscribe` de un clic (RFC 8058) corresponde al envío, no a este módulo, y todavía no está cableado.
- Solo contactos que ya están en el lead. La capa 1 rechaza un correo o un celular inventado en el cuerpo o en el asunto.
- Banda de precio, frases prohibidas, testimonios, largo por canal, mayúsculas y «!!!».
- Enlaces solo al dominio de `public_base_url`.
- Anonimización del prospecto outbound sin interacción a los 120 días.
- Sin pixel. Sin WhatsApp frío. Instagram y LinkedIn en cola manual.
- `OUTREACH_ENABLED=false` y `DRY_RUN=true` por defecto. El Checker no abre sockets y no envía.

Lo que esta capa no hace, y no hay que dar por hecho: frenar un correo freemail que sí esté en el lead, detectar un RUT en el cuerpo, ni decidir si el destinatario es persona natural. Eso queda para quien elige el contacto y para el abogado.

## 7. Ponderación

A favor del responsable: el dato nace de una fuente que el negocio publicó o de una ficha pública; la oferta es B2B y acotada; hay baja, tope de frecuencia y prohibición de inventar contactos; no se venden bases ni se usa pixel.

En contra, y con más peso: no hay relación previa; el titular no pidió el contacto; muchos prospectos son personas naturales; la expectativa razonable no está acreditada; el interés es solo comercial y tiene alternativa (el inbound con consentimiento); la ley hoy vigente se apoya en la autorización; y el volumen previsto convierte un correo aislado en un tratamiento sistemático.

El interés comercial de la agencia no prevalece sobre el derecho del titular a no ser contactado.

## 8. Conclusión conservadora

El interés legítimo no es base operativa. No se usa para justificar `OUTREACH_ENABLED`, ni un envío de prueba a un negocio real, ni una excepción “solo un correo”.

Hasta que un abogado responda por escrito una de estas tres opciones, el sistema se queda en la primera:

1. Outreach apagado.
2. Una franja permitida, con condiciones que este diseño pueda cumplir de verdad.
3. Modelo prohibido.

Si algún día la respuesta fuera la segunda, el máximo que este diseño podría sostener —y que igual habría que revalidar— es estrecho: un correo inicial y dos seguimientos, solo a casillas genéricas publicadas por el propio negocio en su sitio, con la URL de procedencia guardada, con baja en el mismo ciclo y supresión global, sin pixel y sin canales automáticos distintos del correo. Los correos que parecen personales no entran en esa franja por este test. Nada de eso se activa solo porque este archivo existe.

Cualquier compra de base, adivinación de correos, WhatsApp frío o automatización de Instagram o LinkedIn deja este test inválido y sigue rechazada por las reglas del Checker en lo que a esas reglas les toca.
