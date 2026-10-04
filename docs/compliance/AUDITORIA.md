# pendiente de ola 3

Plantilla de auditoría de compliance. Sin firmar. No es un certificado, no es un dictamen y no habilita envíos.

| Campo | Valor |
|---|---|
| Estado | pendiente de ola 3 |
| Auditor | (vacío) |
| Fecha | (vacío) |
| Alcance revisado | (vacío) |
| Resultado | no evaluado |
| Firma | sin firmar |

La completa A8 en la ola 3, con el código ya integrado y la salida real de la suite. Hasta entonces toda casilla queda abierta. Una casilla marcada sin evidencia no cuenta. Los documentos de apoyo son `registro_actividades.md`, `interes_legitimo.md` y `REVISION_LEGAL.md`. Ninguno de los tres cierra la base legal.

## Lista de verificación

- [ ] `is_opt_out` reconoce STOP, BAJA, «no me escriban», «no me escribas», «déjame de escribir», «no me contacten», unsubscribe y remove me, con y sin tildes y mayúsculas, y no marca texto inocente.
- [ ] `suppression_hash` es SHA-256 del valor normalizado y el tipo de contacto no entra al hash. La tabla de supresión no guarda el valor en claro.
- [ ] `check_rules` no aprueba si `agency_name` viene vacío o en blanco, ni si el nombre solo está en el asunto.
- [ ] El opt-out y la baja del correo están en el cuerpo. El asunto no los reemplaza.
- [ ] Un destinatario suprimido no se aprueba, en ningún canal.
- [ ] Un correo o celular que no está en el lead ni en la agencia se rechaza, también si va en el asunto.
- [ ] Precio fuera de banda no se aprueba y queda para HITL. El puntaje de la capa 1 no sirve para saltarse una razón. El prompt viejo que habla de score ≥ 70 no manda sobre esta capa.
- [ ] Frases prohibidas, testimonios inventados, exceso de mayúsculas y tres o más exclamaciones rechazan.
- [ ] Largos: correo 1.200, Instagram 500, LinkedIn 500, WhatsApp 400.
- [ ] WhatsApp saliente sin consentimiento se rechaza. Instagram y LinkedIn no se envían solos (esto se verifica en el sender, no solo en la capa 1).
- [ ] Todo enlace fuera de `public_base_url` se rechaza, incluidos los que solo se parecen al dominio.
- [ ] `looks_like_injection` marca ignorar instrucciones, cambiar el estado del lead, revelar el system prompt y enviar a un tercero. El Checker no obedece ese texto.
- [ ] `engine/core/compliance.py` no abre sockets, no lee el entorno y no envía.
- [ ] `DRY_RUN=true` no abre sockets de salida en los adaptadores (otro dueño; se constata en la ola 3).
- [ ] El opt-out del mismo ciclo corta la secuencia y escribe la supresión (otro dueño; se constata en la ola 3).
- [ ] La capa 1 no frena por sí sola un freemail que ya venga en el lead, ni un RUT en el cuerpo. Decidir si eso se exige antes de encender outreach.
- [ ] El header `List-Unsubscribe` de un clic está en el envío real, no solo la palabra «baja» en el cuerpo.
- [ ] `REVISION_LEGAL.md` fue leído con un abogado y hay respuesta escrita: outreach apagado, franja permitida, o modelo prohibido.
- [ ] El interés legítimo no se usa como base operativa si la respuesta no es la franja permitida.
- [ ] Identidad tributaria completa antes de cualquier cobro real. La boleta o factura del SII sigue en tarea humana hasta que el contador defina la integración.
- [ ] Plazo de caché de Google Places verificado contra los términos vigentes. El rating no se muestra sin atribución.
- [ ] El registro de actividades se actualizó si cambió un tratamiento, un proveedor o un plazo.

## Residuos conocidos

No bloquean la plantilla, pero la ola 3 tiene que decir si se aceptan o se cierran:

- homoglifos (letras cirílicas que parecen latinas) no se normalizan;
- el hash de supresión no tiene sal, a propósito, para poder comparar;
- la procedencia solo está modelada para el correo, no para teléfono ni redes;
- este archivo no revisa db, agentes, `main.py`, contratos ni el dashboard.

## Firma

Sin firmar.

Nombre: ________________________________

Fecha: ________________________________

Firma: ________________________________
