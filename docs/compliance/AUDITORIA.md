# Revisión de ingeniería — 2026-10-04

No es un dictamen de abogado, no es un certificado y no habilita envíos reales. La firma de abajo constata la suite contra el código integrado en `grok/autonomia-041026`. Las casillas legales siguen abiertas a propósito.

| Campo | Valor |
|---|---|
| Estado | revisión de ingeniería |
| Auditor | A0, integrador, en el rol de cierre que la ola 3 asigna a A8 |
| Fecha | 2026-10-04 |
| Alcance revisado | `engine/core/compliance.py`, adaptadores de correo y la suite `engine/tests/test_compliance.py`, `test_email.py` |
| Resultado | las casillas de código marcadas tienen test. Las de abogado quedan abiertas |
| Firma | A0 · 2026-10-04 · no sustituye a `REVISION_LEGAL.md` |

Los documentos de apoyo son `registro_actividades.md`, `interes_legitimo.md` y `REVISION_LEGAL.md`. Ninguno cierra la base legal.

## Lista de verificación

- [x] `is_opt_out` reconoce STOP, BAJA, «no me escriban», «no me escribas», «déjame de escribir», «no me contacten», unsubscribe y remove me, con y sin tildes y mayúsculas, y no marca texto inocente. Tests `test_opt_out_reconoce_mayusculas_y_tildes` y `test_opt_out_no_marca_texto_inocente`.
- [x] `suppression_hash` es SHA-256 del valor normalizado y el tipo de contacto no entra al hash. Test `test_hash_estable_y_normalizacion`.
- [x] `check_rules` no aprueba si `agency_name` viene vacío o en blanco, ni si el nombre solo está en el asunto. Tests `test_agencia_vacia_no_aprueba`, `test_agencia_en_blanco_no_aprueba`, `test_identidad_solo_en_el_asunto_no_basta`.
- [x] El opt-out y la baja del correo están en el cuerpo. El asunto no los reemplaza. Tests `test_opt_out_solo_en_el_asunto_no_basta` y `test_email_sin_baja_no_aprueba`.
- [x] Un destinatario suprimido no se aprueba, en ningún canal. Test `test_rechaza_destinatario_suprimido_y_contacto_inventado`.
- [x] Un correo o celular que no está en el lead ni en la agencia se rechaza, también si va en el asunto. Tests `test_correo_inventado_en_el_asunto` y `test_rechaza_destinatario_suprimido_y_contacto_inventado`.
- [x] Precio fuera de banda no se aprueba y queda para HITL. Tests `test_rechaza_precio_fuera_de_banda` y `test_banda_de_precio`.
- [x] Frases prohibidas, testimonios inventados, exceso de mayúsculas y tres o más exclamaciones rechazan. Tests `test_frases_prohibidas`, `test_testimonios_prohibidos`, `test_rechaza_exceso_de_mayusculas`, `test_rechaza_tres_exclamaciones`.
- [x] Largos: correo 1.200, Instagram 500, LinkedIn 500, WhatsApp 400. Test `test_largo_maximo_por_canal`.
- [x] WhatsApp saliente sin consentimiento se rechaza. Instagram y LinkedIn no se envían solos. Tests `test_rechaza_whatsapp_en_frio` y `test_meta.py` (`manual_pending` en frío).
- [x] Todo enlace fuera de `public_base_url` se rechaza, incluidos los que solo se parecen al dominio. Tests `test_rechaza_enlace_externo` y `test_rechaza_dominio_que_solo_parece_propio`.
- [x] `looks_like_injection` marca ignorar instrucciones, cambiar el estado del lead, revelar el system prompt y enviar a un tercero. Test `test_looks_like_injection_cubre_los_cuatro_intentos`.
- [x] `engine/core/compliance.py` no abre sockets, no lee el entorno y no envía. El módulo solo parsea URLs con `urllib.parse`.
- [x] `DRY_RUN=true` no abre sockets de salida en los adaptadores. Tests `test_dry_run_outreach_no_llama_respx` y `test_transaccional_dry_run_no_llama_respx`.
- [ ] El opt-out del mismo ciclo corta la secuencia y escribe la supresión. Hay piezas en el worker; esta casilla queda abierta hasta una prueba de un ciclo completo dedicada.
- [ ] La capa 1 no frena por sí sola un freemail que ya venga en el lead, ni un RUT en el cuerpo. Decidir si eso se exige antes de encender outreach.
- [x] El header `List-Unsubscribe` de un clic está en el envío. `integrations/email/outreach.py` arma `List-Unsubscribe` y `List-Unsubscribe-Post`. Test `test_email.py`.
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
