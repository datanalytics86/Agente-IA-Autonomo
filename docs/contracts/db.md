# Contrato de base de datos

SQLAlchemy 2 + Alembic. SQLite por defecto (`engine/state/agencia.db`). PostgreSQL 16 si `DATABASE_URL` empieza por `postgres`. Tiempos en UTC (`DateTime(timezone=True)`). JSON con el tipo `JSON` de SQLAlchemy. Claves primarias `str` (uuid4 hex, prefijo corto opcional).

Escrituras en transacción. En Postgres, tomar trabajo pendiente usa `SELECT … FOR UPDATE SKIP LOCKED`. En SQLite, la misma operación es una transacción inmediata sobre filas `status='queued' AND scheduled_at <= now`.

## leads

| Columna | Tipo | Notas |
|---|---|---|
| id | str PK | |
| source | str | `outbound_places` `outbound_demo` `inbound_diagnostico` `inbound_contacto` `inbound_whatsapp` `referido` |
| business | str | |
| category | str | slug de `dominio.md` |
| city | str | |
| commune | str | |
| address_public | str null | |
| place_id | str null UNIQUE | |
| google_maps_uri | str null | |
| website_url | str null | |
| website_audit | JSON null | |
| opportunity_score | int | 0–100 |
| rating | float null | |
| reviews | int null | |
| contact_email | str null | |
| contact_email_source_url | str null | |
| instagram_handle | str null | sin `@`, minúsculas |
| linkedin_url | str null | |
| phone_public | str null | |
| consent | JSON null | `{type, text_version, ts, ip_hash}` |
| status | str | índice |
| paused_from | str null | |
| hitl_reason | str null | |
| close_reason | str null | |
| estimated_value_clp | int | |
| high_value | bool | |
| tone | str | `tu` o `usted` |
| diagnosis | JSON null | también markdown en `diagnosis.markdown` |
| next_action_at | datetime null | índice |
| created_at | datetime | |
| updated_at | datetime | |
| anonymized_at | datetime null | |

Índice único parcial: nombre normalizado (minúsculas, sin tildes) + `commune` donde `anonymized_at IS NULL`, implementado en aplicación y con índice `(commune, business)`.

## lead_events

`id`, `lead_id` FK, `from_status`, `to_status`, `actor`, `reason`, `ts`. Índice `(lead_id, ts)`.

## messages

`id`, `lead_id` FK, `thread_id`, `direction` (`out`|`in`), `channel` (`email_outreach`|`email_tx`|`instagram`|`linkedin`|`whatsapp`|`web_form`), `sequence_step` int null, `status` (`draft`|`checking`|`approved`|`rejected`|`queued`|`manual_pending`|`sent`|`manual_sent`|`delivered`|`bounced`|`failed`|`received`|`blocked`), `subject`, `body_text`, `body_html`, `check_result` JSON, `provider_message_id` UNIQUE null, `scheduled_at`, `sent_at`, `intent`, `intent_confidence` float null, `created_at`.

Índice `(channel, status, scheduled_at)`.

## approvals

`id`, `lead_id` FK, `kind` (`deal_alto_valor`|`tasa_respuesta_baja`|`baja_confianza`|`compliance`|`fuera_de_alcance`|`error_sistema`|`tarea_manual`), `payload` JSON, `status` (`pending`|`approved`|`rejected`|`edited`), `decided_by`, `decided_at`, `decision_note`, `created_at`.

## artifacts

`id`, `lead_id` FK null, `project_id` FK null, `kind` (`landing_demo`|`landing_prod`|`storyboard`|`video`|`screenshot`|`reporte`|`propuesta`), `version` int, `path`, `public_token` UNIQUE, `expires_at`, `meta` JSON.

## orders

`id`, `lead_id` FK, `package_code`, `amount_clp`, `iva_clp`, `total_clp`, `deposit_percent`, `status` (`pending`|`deposit_paid`|`paid`|`refunded`|`cancelled`), `checkout_url`, `provider_preference_id`, `created_at`.

## payments

`id`, `order_id` FK, `provider`, `provider_payment_id` UNIQUE, `status`, `amount_clp`, `raw` JSON, `received_at`.

## projects

`id`, `order_id` FK UNIQUE, `lead_id` FK, `status` (`intake_pendiente`|`en_produccion`|`en_revision_cliente`|`aprobado`|`publicado`), `intake` JSON, `revisions_used` int default 0, `max_revisions` int, `domain`, `deploy_url`, `portal_token` UNIQUE, `delivered_at`.

## suppression

`id`, `kind` (`email`|`domain`|`instagram`|`linkedin`|`phone`), `value_hash` char(64), `reason`, `source`, `created_at`. UNIQUE `(kind, value_hash)`. El hash es SHA-256 del valor normalizado (email en minúsculas; dominio sin esquema; teléfono solo dígitos con prefijo 56).

## data_requests

`id`, `kind` (`acceso`|`rectificacion`|`supresion`|`oposicion`|`portabilidad`|`bloqueo`), `requester_email`, `details`, `status` (`open`|`done`|`rejected`), `due_at`, `resolved_at`. Plazo default 30 días.

## llm_calls

`id`, `agent`, `model`, `prompt_name`, `prompt_version`, `tokens_in`, `tokens_out`, `cost_usd` numeric, `latency_ms`, `ok` bool, `error`, `lead_id` null, `ts`.

## job_runs

`id`, `job`, `started_at`, `finished_at`, `status` (`running`|`ok`|`error`), `processed` int, `error`.

## events

Reemplaza `logs.json`. Sin tope de filas. `id`, `ts`, `agent`, `level` (`debug`|`info`|`warn`|`error`), `message`, `lead_id` null, `meta` JSON. Retención por `RETENTION_DAYS` solo para niveles `debug` e `info` de prospectos ya anonimizados; `warn` y `error` se conservan.

## settings_kv

`key` PK, `value` JSON, `updated_by`, `updated_at`.

Claves reservadas: `kill_switch` (bool, default false), `quotas` (objeto), `prices` (objeto de paquetes), `hitl_response_rate_by_channel` (objeto), `video_enabled` (bool, default true).

## users

`id`, `email` UNIQUE, `password_hash` (argon2), `last_login_at`. Una sola fila de admin en esta versión.

## Tablas de soporte (no estaban en el mínimo; hacen falta para idempotencia y el lock)

### webhook_events

`id`, `provider`, `event_id`, `received_at`. UNIQUE `(provider, event_id)`.

### worker_lock

Una fila `id=1`, `owner` str, `heartbeat_at`. El worker renueva el heartbeat; si tiene más de 60 s, otro proceso puede tomarlo.

## Migración JSON

`--mode migrate-json`:

1. Copia `leads.json` y `logs.json` a `engine/state/backup/<timestamp>/` antes de tocar la BD.
2. Inserta leads y eventos. Idempotente por `id`: si ya existe, no lo pisa.
3. No borra ni reescribe el JSON de origen.
4. Un registro que no valida se cuenta en el reporte y se deja en el JSON. No se descarta en silencio.
5. JSON ilegible: aborta sin escribir la BD y sin truncar el archivo. Código de salida 1.

## Repositorios (`engine/db/repositories.py`)

A1 expone estas clases. El resto del sistema no ejecuta SQL suelto.

- `LeadRepository.get/list/add/save`
- `transition` vive en `engine/core/states.py` y usa la sesión del repositorio
- `MessageRepository`, `ApprovalRepository`, `ArtifactRepository`, `OrderRepository`, `PaymentRepository`, `ProjectRepository`
- `SuppressionRepository.contains(kind, raw_value)`, `add(...)`
- `SettingsRepository.get/put` con default si la clave no existe
- `EventRepository.append/list`
- `LlmCallRepository.add/spend_today_usd`
- `JobRunRepository`
- `DataRequestRepository`
