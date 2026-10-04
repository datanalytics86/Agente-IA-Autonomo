# Modelo de amenazas (STRIDE breve)

Fecha de revisión: 2026-10-04. Alcance: API, worker, sitio público, dashboard y adaptadores. El modo demo no abre red de outreach ni cobra.

## API y webhooks

| Amenaza | Qué puede pasar | Control |
|---|---|---|
| Spoofing | Un webhook falso marca un pago o una agenda | Firma HMAC por proveedor. Mercado Pago además se consulta con `fetch_payment`. Secreto vacío rechaza. |
| Tampering | Reenviar un evento ya procesado | `webhook_events` único por proveedor e id |
| Repudiation | No queda quién cambió un lead | `lead_events` y `events` con actor y motivo |
| Information disclosure | La demo o el portal se indexan | `X-Robots-Tag: noindex` en `/demo` y en la vista previa. `robots.txt` bloquea `/demo`, `/proyecto` y `/u` |
| Denial of service | Formularios públicos o login a fuerza bruta | Rate limit de login (5 / 15 min), honeypot y Turnstile. En demo el Turnstile vacío se acepta; en prod sin secreto se rechaza |
| Elevation | CSRF contra el admin | Cookie de sesión HttpOnly y token CSRF en métodos que escriben |

## Datos y compliance

| Amenaza | Qué puede pasar | Control |
|---|---|---|
| Information disclosure | Correos o teléfonos en claro en la base o en logs | Supresión guarda SHA-256 del valor normalizado. Los tests no imprimen secretos |
| Tampering | Un mensaje entrante o un HTML piden ignorar las reglas | Los prompts marcan el contenido externo como no confiable. El checker de reglas puede rechazar sin el juez |
| Spoofing | Outreach frío por Instagram, LinkedIn o WhatsApp | Esos canales salen `manual_pending`. WhatsApp no se usa en frío. El envío real exige `APP_MODE=prod`, `OUTREACH_ENABLED=true`, `kill_switch=true` y credencial |

## Sitio, landings y hosting

| Amenaza | Qué puede pasar | Control |
|---|---|---|
| Tampering | Publicar un dominio que el cliente no aprobó | `domain_allowed` solo con dominio autorizado o proyecto `aprobado` / `publicado` |
| Information disclosure | Inventar RUT, dirección o testimonios | Identidad vacía y placeholder «[datos de la agencia]». El build del sitio lo vigila |
| Denial of service | Copiar un `project_id` con `..` | `project_slug` rechaza separadores y el destino tiene que quedar dentro del directorio de clientes |

## Dashboard

| Amenaza | Qué puede pasar | Control |
|---|---|---|
| Spoofing | Sesión robada | Cookie HttpOnly, SameSite=Lax, Secure solo fuera de demo |
| Elevation | El cliente del dashboard pinta números inventados | Las métricas salen de `GET /api/metrics`. Zustand no guarda leads |

## Residual

Docker no está instalado en la máquina de integración, así que el healthcheck de Compose no tiene evidencia local. Los headers de seguridad del sitio en producción los pone Caddy; en el e2e el sitio estático de Astro no pasa por Caddy.
