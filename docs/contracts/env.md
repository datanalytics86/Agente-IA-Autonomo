# Contrato de entorno

Archivo canónico: `/.env.example`. `engine/.env.example` es una copia idéntica porque el CLI histórico carga `engine/.env`. `core/config.py` (pydantic-settings) lee, en orden, `engine/.env` y el `.env` de la raíz. Las variables de proceso ganan.

Todo umbral vive aquí y puede taparse en runtime con `settings_kv` (kill switch, cuotas, precios, tasa HITL por canal). El código no hardcodea estos números.

`APP_MODE=demo`, `DRY_RUN=true` y `OUTREACH_ENABLED=false` son el default. Sin credenciales el proceso arranca igual.

## Grupos

### Modo

| Variable | Default | Notas |
|---|---|---|
| APP_MODE | demo | `demo` o `prod` |
| DRY_RUN | true | bool. Con true ningún adaptador abre socket de salida |
| OUTREACH_ENABLED | false | bool |
| TZ | America/Santiago | |
| VIDEO_ENABLED | true | false permite `landing → pitch_listo` |

### Núcleo

| Variable | Default |
|---|---|
| DATABASE_URL | `sqlite:///./state/agencia.db` (relativo a `engine/`) |
| SECRET_KEY | vacío hasta go-live. En demo, si está vacío, se deriva un valor de proceso no persistido y se avisa en el log |
| ADMIN_EMAIL | vacío |
| ADMIN_PASSWORD_HASH | vacío (argon2). Lo escribe `--mode create-admin` |
| PUBLIC_BASE_URL | `http://localhost` |
| ADMIN_BASE_URL | `http://localhost:8080` |
| CORS_ORIGINS | `http://localhost:8080,http://localhost:4321` |

### Agencia

`AGENCY_NAME`, `AGENCY_LEGAL_NAME`, `AGENCY_RUT`, `AGENCY_EMAIL`, `AGENCY_ADDRESS`. Todas vacías. La UI muestra el placeholder «completa los datos de la agencia». Prohibido inventar nombre, RUT o dirección.

### LLM

| Variable | Default |
|---|---|
| XAI_API_KEY | vacío. Alias aceptado: `GROK_API_KEY` |
| LLM_BASE_URL | `https://api.x.ai/v1` |
| LLM_MODEL | `grok-4.7` |
| LLM_MODEL_FAST | `grok-4.6` |
| LLM_DAILY_BUDGET_USD | 3 |

El código lee el nombre del modelo desde la config. No hay un string de modelo suelto en los agentes.

### Datos y scout

| Variable | Default |
|---|---|
| GOOGLE_PLACES_API_KEY | vacío |
| PAGESPEED_API_KEY | vacío |
| SCOUT_COMMUNES | Providencia,Las Condes,Ñuñoa,Maipú,Viña del Mar,Valparaíso,Concepción,Temuco,La Serena |
| SCOUT_CATEGORIES | los 15 slugs de `dominio.md`, separados por coma |
| SCOUT_DAILY_LIMIT | 30 |
| SCOUT_MIN_RATING | 4.0 |
| SCOUT_MIN_REVIEWS | 15 |
| DIAGNOSE_DAILY_LIMIT | 15 |

### Email

`RESEND_API_KEY`, `EMAIL_TX_FROM`, `OUTREACH_SMTP_HOST`, `OUTREACH_SMTP_PORT` (587), `OUTREACH_SMTP_USER`, `OUTREACH_SMTP_PASSWORD`, `OUTREACH_IMAP_HOST`, `OUTREACH_IMAP_PORT` (993), `OUTREACH_IMAP_USER`, `OUTREACH_IMAP_PASSWORD`, `OUTREACH_FROM`, `EMAIL_OUTREACH_DAILY_LIMIT` (15), `EMAIL_OUTREACH_DAILY_MAX` (50), `FOLLOWUP_1_BUSINESS_DAYS` (4), `FOLLOWUP_2_BUSINESS_DAYS` (9).

Resend y el resto de transaccionales no se usan para outreach en frío.

### Agenda, pagos, Meta, seguridad, hosting, avisos, HITL

Ver la tabla §8.8 del megaprompt. Defaults repetidos aquí para que el contrato se baste:

- `BOOKING_PROVIDER=calcom` (`calcom`|`calendly`). `BOOKING_LINK` alias histórico `CALENDLY_LINK`.
- `DEPOSIT_PERCENT=50`, `PRICES_INCLUDE_IVA=true`, `PRICE_MIN_CLP=250000`, `PRICE_MAX_CLP=450000`, `MAINTENANCE_PRICE_CLP` vacío.
- `HITL_VALUE_CLP=2800000`, `HITL_RESPONSE_RATE=0.12`, `HITL_MIN_SAMPLE=30`, `MOBILE_AUTOREPLY_MIN_CONFIDENCE=0.8`.
- `DEMO_TTL_DAYS=30`, `RETENTION_DAYS=120`, `JOB_MAX_RETRIES=3`.
- `HOSTING_PROVIDER=caddy`, `CLIENT_SITES_DIR=engine/output/clients`.
- `NOTIFY_EMAIL` vacío. Telegram vacío = digest solo por log.

Bools de pydantic-settings aceptan `true/false/1/0`.
