# GO_LIVE — checklist del dueño

Orden obligatorio. No marques un paso sin haberlo hecho. El sistema funciona en demo sin ninguno de estos datos.

1. **Identidad.** Completar `AGENCY_NAME`, `AGENCY_LEGAL_NAME`, `AGENCY_RUT`, `AGENCY_EMAIL`, `AGENCY_ADDRESS`.
2. **SII.** Inicio de actividades y método de boleta o factura electrónica. Cada pago abre una tarea HITL para emitir el documento. Integración automática: pendiente de decisión del contador.
3. **Revisión legal.** Leer `docs/compliance/REVISION_LEGAL.md` con un abogado (privacidad, términos, consentimiento, baja).
4. **Dominios.** Un `.cl` en NIC Chile para el sitio y un dominio secundario solo para outreach.
5. **VPS y DNS.** Máquina de 2 GB, registros A/AAAA y CNAME, `docker compose -f infra/docker-compose.yml up -d`.
6. **Buzón de outreach.** Google Workspace o Zoho en el dominio secundario. SPF, DKIM y DMARC. Warm-up de 2 a 3 semanas antes de prospectar.
7. **Correo transaccional.** Cuenta Resend con el dominio principal verificado. No usar Resend para frío.
8. **Llaves.** xAI con tope de gasto. Google Places con cuota y alerta de facturación. PageSpeed.
9. **Agenda y cobro.** Cal.com o Calendly con webhook. Mercado Pago de producción y secreto de webhook.
10. **Opcional.** App de Meta para Instagram y WhatsApp inbound, Turnstile, Telegram para el digest.
11. **Admin.** `python main.py --mode create-admin` con `ADMIN_EMAIL`.
12. **Escalamiento.** Seguir el plan de abajo. No saltar al automático.

## Escalamiento

1. **Sombra (semanas 1–2).** `APP_MODE=prod`, `DRY_RUN=true`. Datos reales. El humano revisa el 100 % en la bandeja HITL.
2. **Semi-automático (semanas 3–4).** `DRY_RUN=false`, `OUTREACH_ENABLED=true`, cupo de 10 correos al día, muestreo humano.
3. **Automático.** Rampa de warm-up hasta `EMAIL_OUTREACH_DAILY_MAX`. El humano atiende HITL, la cola manual y el digest.

## Qué falta cablear cuando existan credenciales

Esta sección la van completando los agentes al dejar un adaptador real. Cada fila es un paso, no un bloqueo de la demo.

| Adaptador | Variable | Estado |
|---|---|---|
| LLM xAI | `XAI_API_KEY` | fake si está vacía |
| Google Places | `GOOGLE_PLACES_API_KEY` | fake si está vacía |
| PageSpeed | `PAGESPEED_API_KEY` | heurística local si está vacía |
| Resend | `RESEND_API_KEY` | fake si está vacía |
| SMTP/IMAP outreach | `OUTREACH_SMTP_*` / `OUTREACH_IMAP_*` | fake si están vacías |
| Cal.com / Calendly | `BOOKING_LINK` + secreto | fake si están vacíos |
| Mercado Pago | `MP_ACCESS_TOKEN` | fake si está vacío |
| Meta | `META_APP_SECRET` | fake si está vacío |
| Caddy ask | red interna | local en Compose |
