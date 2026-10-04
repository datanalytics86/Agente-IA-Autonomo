# Decisiones

Registro de A0. Lo ya cerrado no se vuelve a discutir. Lo nuevo se agrega al final.

## ADR-001 — Arquitectura fija (§4)

Se adopta tal cual el cuadro de `instrucciones041026.md` §4: FastAPI, SQLAlchemy 2 + Alembic, pydantic-settings, APScheduler en `America/Santiago`, cliente OpenAI-compatible hacia xAI, Jinja2 con autoescape, Playwright + FFmpeg, Astro para el sitio, TanStack Query en el dashboard, dos canales de email, Cal.com por defecto, Mercado Pago Checkout Pro, Meta solo inbound, Caddy on-demand TLS, Compose con `db` `api` `worker` `caddy`.

## ADR-002 — Defaults de negocio (§8.9)

| Paquete | Precio | Incluye |
|---|---|---|
| landing_esencial | 250.000 CLP | Landing de 5 secciones, publicación, 1 revisión |
| landing_pro | 350.000 CLP | Esencial + video 12 s + formulario + WhatsApp del cliente, 2 revisiones |
| landing_premium | 450.000 CLP | Pro + SEO local + schema.org, 3 revisiones |
| multi_sede | a cotizar | Siempre HITL |

Anticipo 50 %, saldo antes de publicar. IVA 19 % incluido mientras `PRICES_INCLUDE_IVA=true`. Mantención oculta hasta que exista `MAINTENANCE_PRICE_CLP`.

## ADR-003 — Umbral de respuesta en frío

En email B2B en frío las tasas suelen estar bastante por debajo del 12 %. El default `HITL_RESPONSE_RATE=0.12` va a pausar el canal con frecuencia en cuanto haya 30 envíos. Queda configurable por canal (`settings_kv.hitl_response_rate_by_channel`) y hay que recalibrarlo con datos reales antes del modo automático. No se baja el default en código.

## ADR-004 — Ownership extra

| Ruta | Dueño | Motivo |
|---|---|---|
| `engine/main.py` | A0 | Punto único de CLI. Los modos nuevos son imports perezosos |
| `engine/pyproject.toml`, `engine/requirements.txt` | A1 | F1-01 |
| `engine/core/compliance.py` | A8 | Veto de compliance. A1 no crea ese archivo |
| `/.env.example` y `engine/.env.example` | A0 | Deben permanecer idénticos |
| `.gitignore` | A0 | |

## ADR-005 — Kill switch

`settings_kv.kill_switch=true` significa envío armado. El default es `false` (detenido). Apagarlo detiene todo envío en el tick siguiente. Hace falta además `APP_MODE=prod`, `OUTREACH_ENABLED=true` y la credencial del canal.

## ADR-006 — Modelos LLM

Default de octubre 2026 según docs.x.ai: `LLM_MODEL=grok-4.7`, `LLM_MODEL_FAST=grok-4.6`, base `https://api.x.ai/v1`. `GROK_API_KEY` es alias de `XAI_API_KEY`. El código no nombra modelos por su cuenta.

## ADR-007 — Slugs de rubro

Quince slugs ASCII únicos, tabla en `docs/contracts/dominio.md`. Reemplazan los slugs repetidos del scout demo (`salud`, `belleza`, `gastronomía`).

## ADR-008 — Identidad de la agencia

Nombre, razón social, RUT, email y dirección quedan vacíos. Textos legales usan el placeholder «[datos de la agencia]». No se inventan.

## ADR-009 — Documento tributario

Al confirmar un pago se abre un approval `tarea_manual` «emitir boleta o factura en el SII». No hay integración con el SII en esta versión.

## ADR-011 — CI de la ola 1

Hasta que A3 deje `engine/agents/` en verde, el job de engine corre `ruff` y `mypy` sobre `core`, `db`, `migrations` y `tests`, no sobre `agents/`. La DoD final sigue exigiendo `ruff check .` y `mypy` en todo el motor. A9 amplía el job en la ola 3.

## ADR-012 — Agenda del diagnóstico gratis

La tabla de §8.2 no tiene salida desde `diagnosticado` hacia la venta, y la aceptación de F4 pide diagnóstico → email → agenda → checkout. El inbound no pasa por el pitch. Se agrega solo la arista `diagnosticado → agendado`, y únicamente la dispara un webhook de agenda firmado que trae `lead_id`. Checkout pasa de `agendado` a `propuesta` salvo alto valor, que va a `revision`. El pago verificado abre el proyecto. El intake deja la vista previa y `en_revision_cliente`. Aprobar copia el HTML a `CLIENT_SITES_DIR/<slug>` y marca `publicado`.

## ADR-013 — Alcance de mypy

Reemplazado en la ronda 2 (`33fc67f`, integrado en `f750250`). `mypy .` revisa todo el motor. Quedan fuera solo `tests/` y `migrations/`. Strict sigue limitado a `core/`, `db/` y `worker/`, declarado flag por flag: en mypy 2.4 un `strict = true` dentro de un override enciende el modo estricto de todo el proyecto. `warn_redundant_casts` es global. El único `ignore_missing_imports` es `apscheduler.*`. En el árbol con wiring de producción: `Success: no issues found in 104 source files`.

## ADR-010 — Lighthouse en CI

La DoD pide Lighthouse móvil ≥ 90 en `/` y en una landing. En CI se corre contra el servidor estático del build (sin red externa). Si el binario de Chrome no está en el runner, el job lo instala. No se relaja el umbral.
