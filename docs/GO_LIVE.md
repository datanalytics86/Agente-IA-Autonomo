# GO_LIVE — checklist del dueño

Orden. No marcar un paso sin haberlo hecho. La demo corre sin estos datos. El despliegue está en `docs/DEPLOY_VPS.md`. El arranque de producción no es `docker compose -f infra/docker-compose.yml up -d`: son los dos archivos de Compose, el `.env` de la raíz y `--build`.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

No inventar nombre, RUT ni dirección. Si un dato de identidad no existe, el sitio dice `[datos de la agencia]`. No es un nombre comercial.

## Checklist

1. **Identidad, solo si ya es real.** `AGENCY_NAME`, `AGENCY_LEGAL_NAME`, `AGENCY_RUT`, `AGENCY_EMAIL`, `AGENCY_ADDRESS`. Las pone el dueño en el `.env`. El motor las lee en runtime. `AGENCY_NAME` y `AGENCY_EMAIL` vacías impiden el arranque en `APP_MODE=prod` (`falta AGENCY_NAME`, `falta AGENCY_EMAIL`). El HTML público se compila en `infra/Dockerfile.front`, que hoy solo recibe `PUBLIC_BASE_URL`. Con ese build el sitio sigue mostrando `[datos de la agencia]` aunque el `.env` del motor ya tenga los datos. No completar el HTML a mano con datos inventados. `SITE_BUILD=prod` fuera de esa imagen aborta si faltan `AGENCY_NAME` o `AGENCY_EMAIL`.

2. **SII.** Inicio de actividades y método de boleta o factura electrónica. Cada pago deja una tarea HITL para emitir el documento. No hay integración automática con el SII.

3. **Revisión legal. Pendiente.** Leer `docs/compliance/REVISION_LEGAL.md` con un abogado (privacidad, términos, consentimiento, baja). Este archivo no la da por hecha y no habilita el outreach.

4. **Dominios.** Un `.cl` en NIC Chile para el sitio. Otro dominio, distinto, solo para el buzón de outreach. `SITE_DOMAIN` es el host del `.cl`. `PUBLIC_BASE_URL` es `https://` más ese host (tiene que empezar por `https`; si no, el proceso no arranca).

5. **VPS, firewall y DNS.** Máquina Ubuntu con Docker, SSH, 80 y 443. A y AAAA de `SITE_DOMAIN` al VPS. El panel es `https://<SITE_DOMAIN>/admin/`, no la raíz del sitio y no `ADMIN_DOMAIN`. `ADMIN_DOMAIN` solo excluye ese host de los sitios de clientes; si no se define, queda `admin.invalid`. Seguir `docs/DEPLOY_VPS.md`. Postgres en prod no publica puertos.

6. **Variables sin las cuales prod no arranca.** El mensaje es `APP_MODE=prod no arranca: …`.

   | Variable | Dónde sale | Qué llena |
   |---|---|---|
   | `APP_MODE` | la fija el dueño | `prod`. La imagen trae `demo` si el `.env` no la pisa |
   | `SECRET_KEY` | generarla (32 caracteres o más). No es de un proveedor | firma de sesión y de tokens de baja |
   | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | las elige el dueño. Sin default en prod: Compose aborta | usuario de la base. Una clave con `@`, `:`, `/` o `#` va ya codificada |
   | `DATABASE_URL` | Compose la arma hacia el servicio `db` | el proceso. Si falta fuera de Compose: `falta DATABASE_URL` |
   | `ADMIN_EMAIL` | el correo del único admin | fail-fast y `create-admin` |
   | `ADMIN_PASSWORD_HASH` | argon2, desde `engine/` con el venv: `python -c "from api.security import hash_password; print(hash_password('la-clave'))"` | solo el fail-fast. El login no la lee |
   | `PUBLIC_BASE_URL` | `https://<SITE_DOMAIN>` | enlaces públicos y cookie `Secure` |
   | `AGENCY_NAME`, `AGENCY_EMAIL` | los datos del paso 1, cuando existan | fail-fast y correos del motor |

   `ADMIN_PASSWORD` es la clave en claro y solo la usa `create-admin`. No va en el `.env` de ejemplo ni se imprime. Ver el paso 14.

7. **Buzón de outreach.** Google Workspace o Zoho, en el dominio secundario. SPF, DKIM y DMARC en el DNS de ese dominio. Warm-up de 2 a 3 semanas antes de prospectar. No usar este buzón en Resend ni al revés.

   | Variable | Dónde sale |
   |---|---|
   | `OUTREACH_SMTP_HOST`, `OUTREACH_SMTP_PORT` (587), `OUTREACH_SMTP_USER`, `OUTREACH_SMTP_PASSWORD` | SMTP del buzón |
   | `OUTREACH_IMAP_HOST`, `OUTREACH_IMAP_PORT` (993), `OUTREACH_IMAP_USER`, `OUTREACH_IMAP_PASSWORD` | IMAP del mismo buzón |
   | `OUTREACH_FROM` | dirección visible del correo en frío |

   El canal de outreach cuenta como credencial completa con host, usuario y clave SMTP, usuario IMAP, `OUTREACH_FROM` y `PUBLIC_BASE_URL`. Sin eso el estado es `deshabilitado: falta …`.

8. **Correo transaccional.** Cuenta en [Resend](https://resend.com) con el dominio principal verificado. No usar Resend para frío.

   | Variable | Dónde sale |
   |---|---|
   | `RESEND_API_KEY` | API key de Resend |
   | `EMAIL_TX_FROM` | remitente del dominio verificado |
   | `RESEND_WEBHOOK_SECRET` | secreto de firma (Svix) del webhook. El código lo lee de esa variable. La URL es `https://<SITE_DOMAIN>/webhooks/email` |

9. **LLM.** [console.x.ai](https://console.x.ai), con tope de gasto. `XAI_API_KEY`. `GROK_API_KEY` es alias y llena la misma variable. `LLM_DAILY_BUDGET_USD` sale en 3.

10. **Datos de prospección.** Google Cloud, con cuota y alerta de facturación. `GOOGLE_PLACES_API_KEY` (Places). `PAGESPEED_API_KEY` (PageSpeed Insights). Sin la key el auditor no pasa a `deshabilitado`: en prod con `DRY_RUN=false` queda `real`.

11. **Agenda.** Uno de los dos.

    - Cal.com (`app.cal.com`): `BOOKING_PROVIDER=calcom`, `BOOKING_LINK`, `CALCOM_WEBHOOK_SECRET`. Webhook `https://<SITE_DOMAIN>/webhooks/calcom`.
    - Calendly: `BOOKING_PROVIDER=calendly`, `BOOKING_LINK` (alias histórico `CALENDLY_LINK`), `CALENDLY_WEBHOOK_SIGNING_KEY`. Webhook `https://<SITE_DOMAIN>/webhooks/calendly`.

12. **Cobro.** Mercado Pago de producción, no el de prueba. `MP_ACCESS_TOKEN` (credenciales de producción). `MP_WEBHOOK_SECRET` (firma). URL `https://<SITE_DOMAIN>/webhooks/mercadopago`. El proceso no confía en el cuerpo: consulta el pago. `DEPOSIT_PERCENT` sale en 50. Precios publicados: `PRICE_MIN_CLP` 250000 y `PRICE_MAX_CLP` 450000. No bajarlos para «probar».

13. **Opcionales.** Sin la credencial, el canal queda deshabilitado y se ve en `/admin/agentes`.

    | Canal | Dónde sale | Variables |
    |---|---|---|
    | Meta (Instagram y WhatsApp de entrada) | app en Meta for Developers | `META_APP_SECRET`, `META_VERIFY_TOKEN`, `IG_ACCESS_TOKEN`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`. Verificación `GET /webhooks/meta`, eventos `POST /webhooks/meta` |
    | Turnstile | Cloudflare, producto Turnstile | `TURNSTILE_SECRET_KEY` en el motor. `TURNSTILE_SITE_KEY` y, en el build del sitio, `PUBLIC_TURNSTILE_SITE_KEY`. Sin secreto el backend no exige token. Con secreto y sin widget en el HTML, el formulario responde 403. La imagen actual no recibe la site key |
    | Aviso al dueño | Resend ya configurado, o BotFather | `NOTIFY_EMAIL` (usa Resend y `EMAIL_TX_FROM`) y/o `TELEGRAM_BOT_TOKEN` más `TELEGRAM_CHAT_ID`. Con uno de los dos el notifier puede quedar `real` |

    Instagram y LinkedIn en frío no se envían solos: quedan en la bandeja manual (`/admin/manual`). WhatsApp nunca en frío, ni automático ni a mano.

14. **Admin.** En el contenedor, no interactivo. Imprime `admin creado: <correo>` o `admin actualizado: <correo>`. No imprime la clave. El login usa la tabla `users`.

    ```bash
    docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T -e ADMIN_PASSWORD api python main.py --mode create-admin
    ```

15. **Escalamiento.** No saltar al automático. No bajar el cupo, ni la tasa 0.12, ni `HITL_VALUE_CLP`. Los valores que salen del código son `EMAIL_OUTREACH_DAILY_LIMIT=15`, `EMAIL_OUTREACH_DAILY_MAX=50`, `HITL_RESPONSE_RATE=0.12`, `HITL_VALUE_CLP=2800000`, `HITL_MIN_SAMPLE=30`. No poner el cupo en 10 ni editar esos umbrales hacia abajo en `/admin/config`.

## Escalamiento

Un envío real de outreach pide las cuatro cosas a la vez: `APP_MODE=prod`, `OUTREACH_ENABLED=true`, `kill_switch` en true y la credencial SMTP de arriba. `DRY_RUN=true` bloquea el socket aunque esas cuatro pasen. `kill_switch` nace en false (detenido). El interruptor no frena el inbound ni los jobs de cumplimiento.

1. **Sombra.** `APP_MODE=prod`, `DRY_RUN=true`, `OUTREACH_ENABLED` sigue en false, kill switch en false. Puede haber datos reales de Places. No hay socket de salida. El dueño revisa la bandeja HITL (`/admin/hitl`) y los borradores. El cupo sigue en 15, la tasa en 0.12 y el umbral de valor en 2.800.000 CLP.

2. **Semi-automático.** Recién después del warm-up del buzón. `DRY_RUN=false`, `OUTREACH_ENABLED=true`, kill switch en true, credencial completa. El cupo no se baja: sigue 15 por día. Un deal de 2.800.000 CLP o más va a revisión antes de salir. Si el canal lleva al menos 30 envíos y la tasa queda bajo 0.12, el job de guarda lo pausa. El dueño sigue la bandeja HITL. Instagram y LinkedIn en frío siguen en la bandeja manual. WhatsApp no se usa en frío.

3. **Automático.** No se tocan la tasa ni `HITL_VALUE_CLP`. Los lunes a las 07:00 (`America/Santiago`) `warmup_ramp` sube el cupo de a 5 hasta `EMAIL_OUTREACH_DAILY_MAX` (50). No subir el tope a mano para saltear la rampa. El dueño atiende HITL, la bandeja manual y el digest.

## Canales sin credencial

No es un bloqueo de la demo. En prod, `/api/agents` y `/admin/agentes` muestran `real`, `dry_run` o `deshabilitado: falta X`.

| Canal | Variable que lo habilita | Sin ella |
|---|---|---|
| LLM xAI | `XAI_API_KEY` | `build_llm` devuelve `FakeLlm` y no llama a xAI. Tampoco llama si `DRY_RUN=true` o si `APP_MODE` no es `prod`. No está en la lista de `/api/agents` |
| Google Places | `GOOGLE_PLACES_API_KEY` | `deshabilitado: falta GOOGLE_PLACES_API_KEY` |
| PageSpeed | `PAGESPEED_API_KEY` | no pasa a `deshabilitado`. En prod con `DRY_RUN=false` el auditor queda `real` |
| Resend | `RESEND_API_KEY` y `EMAIL_TX_FROM` | transaccional deshabilitado. Nunca es el canal de frío |
| SMTP/IMAP | las de outreach del paso 7 | `deshabilitado: falta …` |
| Cal.com o Calendly | `BOOKING_LINK` y el secreto del proveedor elegido | deshabilitado |
| Mercado Pago | `MP_ACCESS_TOKEN` | deshabilitado |
| Meta | `META_APP_SECRET` y `META_VERIFY_TOKEN` | deshabilitado. No abre frío de Instagram, LinkedIn ni WhatsApp |
| Caddy | nada, si `HOSTING_PROVIDER=caddy` | el volumen `client_sites` |
| Aviso al dueño | `NOTIFY_EMAIL` con Resend, o Telegram | `deshabilitado: falta NOTIFY_EMAIL, …` |
