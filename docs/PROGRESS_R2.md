# PROGRESS — Ronda 2 deploy 04-10-2026

Rama: `grok/deploy-r2-041026` · Base: `main` en `d5dcc6b` · HEAD de trabajo: `d4363aa` más `engine/tests/test_coverage_floors.py` (aún sin commit) · Ola actual: cierre de DoD

## Estado de la DoD (§8)

A ✅ · B ✅ · C ✅ · D ☐ · E ✅ · F ✅ · G ✅ · H ☐ · I ☐

Docker local: el comando `docker` no existe en esta máquina. `docker compose ... config` se validó con el binario Compose v5.6.0 (no hace falta el daemon). El smoke §7.2 sigue siendo el job `compose-smoke`. La corrida verde conocida es https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37247682028 sobre `00190b0`. Ese SHA no incluye el embudo de B3 ni el arnés de simulación. D e I quedan abiertos hasta un run verde del HEAD que se empuje.

## Línea base de cobertura (sin el test de 14 días)

`pytest -q -k "not catorce_dias" --cov=core --cov=db --cov=api --cov=agents --cov=integrations --cov=worker --cov=simulation`: **316 passed**, 1 deselected, **89 %** (9215 stmts, 1049 miss). Por archivo del G20: `services.py` 96 %, `security.py` 82 %, `closer.py` 100 %, `delivery.py` 100 %, `wiring.py` 92 %.

`mypy .`: Success, 105 source files. `ruff check .` y `ruff format --check .`: limpios.

## Hallazgos G1–G24

| ID | Severidad | Estado | Tarea |
|----|-----------|--------|-------|
| G1 | P0 | ✅ | psycopg y requirements; el smoke verde los ejerce |
| G2 | P0 | ✅ | sitio Astro en Caddy; smoke de `00190b0` |
| G3 | P0 | ✅ | `/admin` con basepath; e2e local 3 passed |
| G4 | P0 | ✅ | TLS y volúmenes en el compose de prod; config válido |
| G5 | P0 | ✅ | `env_file` en api y worker |
| G6 | P0 | ✅ | fail-fast |
| G7 | P0 | ✅ | Alembic al arrancar; el smoke comprueba `alembic_version` |
| G8 | P0 | ✅ | imagen y job `compose-smoke` verde en `00190b0` |
| G9 | P0 | ✅ | wiring |
| G10 | P0 | ✅ | pipeline único; `test_worker_pipeline.py` |
| G11 | P0 | ✅ | entrega con aprobación del cliente |
| G12 | P0 | ✅ | inbound clasificado con Mobile |
| G13 | P0 | ✅ | Mercado Pago |
| G14 | P0 | ✅ | webhooks de correo y Meta |
| G15 | P0 | ✅ | informe de diagnóstico |
| G16 | P0 | ✅ | saldo; `test_publica_solo_con_saldo_pagado` |
| G17 | P1 | ✅ | Turnstile |
| G18 | P1 | ✅ | notifier |
| G19 | P1 | ✅ | mypy del motor |
| G20 | P1 | ✅ | cobertura 89 % y ≥ 80 % en los cinco archivos |
| G21 | P1 | ☐ | CI del HEAD nuevo (openapi, e2e, compose-smoke, engine) |
| G22 | P1 | ✅ | simulación 14 días dentro de `pytest -q --cov --cov-fail-under=85`: 317 passed, violaciones 0 |
| G23 | P1 | ✅ | backup en el smoke de `00190b0` |
| G24 | P1 | ✅ | nota en los docs de la ronda 1 |

G1, G2, G4, G5, G7, G8 y G23 quedan cerrados contra el run `37247682028`. El próximo push tiene que volver a poner ese job en verde sobre el HEAD, porque el worker de la imagen cambió después de `00190b0`.

## Tablero

| ID | Tarea | Agente | Estado | Commit | Evidencia |
|----|-------|--------|--------|--------|-----------|
| R2-B0-00 | Rama y contratos | B0 | ✅ | 589a37a | tablero y contrato de `build_ports` |
| R2-B0-01 | Nota en docs de la ronda 1 | B0 | ✅ | 589a37a | nota al inicio de PROGRESS e INFORME |
| R2-B0-02 | `.env.example` e `infra/.env.ci` | B0 | ✅ | | dominios, Postgres y build del sitio |
| R2-B0-03 | Informe y PR | B0 | ☐ | | `docs/INFORME_FINAL_R2.md` |
| R2-B1-01 | psycopg y requirements | B1 | ✅ | 509cf8f | `test_requirements_cubre_pyproject` |
| R2-B1-02 | Dockerfile.engine | B1 | ✅ | 00190b0 | smoke `37247682028` |
| R2-B1-03 | Dockerfile.front | B1 | ✅ | 00190b0 | smoke `37247682028` |
| R2-B1-04 | Compose base y prod | B1 | ✅ | 00190b0 | smoke y `config` exit 0 |
| R2-B1-05 | Caddyfile | B1 | ✅ | 00190b0 | smoke `37247682028` |
| R2-B1-06 | Backup y restauración | B1 | ✅ | 00190b0 | paso 10 del smoke |
| R2-B1-07 | smoke.py y job CI | B1 | ✅ | 00190b0 | run `37247682028` |
| R2-B2-01 | `build_ports` | B2 | ✅ | 8395337 | `test_prod_ports_no_son_stubs` |
| R2-B2-02 | SMTP con candado | B2 | ✅ | 8395337 | candado abierto y cerrado |
| R2-B2-03 | IMAP sin intención | B2 | ✅ | 8395337 | `test_imap_poller_deja_el_intent_vacio` |
| R2-B2-04 | Resto de adaptadores y notifier | B2 | ✅ | 8395337 | `OwnerNotifier` en prod |
| R2-B2-05 | `build_payments` en la API | B2 | ✅ | 8395337 | `test_checkout_prod_usa_mercadopago` |
| R2-B2-06 | Estado de canales | B2 | ✅ | 8395337 | `test_estado_de_canales` |
| R2-B3-01 | Funnel invoca agentes | B3 | ✅ | b3d9381 | `test_worker_y_demo_usan_los_mismos_agentes` |
| R2-B3-02 | Artefactos en disco | B3 | ✅ | b3d9381 | `test_artifacts_path_existe` |
| R2-B3-03 | Pitch del Diagnoser | B3 | ✅ | b3d9381 | `test_pitch_sin_llm_usa_copywriter` |
| R2-B3-04 | Entrega con aprobación | B3 | ✅ | b3d9381 | `test_entrega_requiere_aprobacion_del_cliente` |
| R2-B3-05 | Saldo | B3 | ✅ | b3d9381 | `test_publica_solo_con_saldo_pagado` |
| R2-B3-06 | Publicación | B3 | ✅ | b3d9381 | el mismo test; no publica con solo el anticipo |
| R2-B4-01 | Clasificar inbound con Mobile | B4 | ✅ | eb07137 | `test_imap_sin_intent_se_clasifica_con_mobile` |
| R2-B4-02 | Webhook de correo | B4 | ✅ | eb07137 | `test_webhook_email_bounce_suprime_y_detiene_secuencia` |
| R2-B4-03 | Webhook de Meta | B4 | ✅ | eb07137 | `test_webhook_meta_crea_mensaje_inbound` |
| R2-B4-04 | Informe de diagnóstico | B4 | ✅ | eb07137 | `test_diagnostico_gratis_envia_informe` |
| R2-B5-01 | Fail-fast de prod | B5 | ✅ | 49c46f9 | `APP_MODE=prod no arranca: falta SECRET_KEY` |
| R2-B5-02 | Base `/admin` | B5 | ✅ | 49c46f9 | vitest 8 passed; e2e 3 passed |
| R2-B5-03 | Turnstile en el sitio | B5 | ✅ | 49c46f9 | sitio 7 passed tras `astro build` |
| R2-B5-04 | Identidad en el build del sitio | B5 | ✅ | 49c46f9 | `SITE_BUILD=prod` sin identidad sale 1 |
| R2-B6-01 | mypy del motor | B6 | ✅ | 33fc67f | `mypy .` 105 archivos en este árbol |
| R2-B6-02 | Cobertura 85 % | B6 | ✅ | | 89 % fuente; pisos del G20 cubiertos |
| R2-B6-03 | CI openapi y e2e | B6 | ☐ | 33fc67f | jobs en ci.yml; falta el run del HEAD |
| R2-B6-04 | Simulación del pipeline real | B6 | ✅ | d4363aa | `reporte_seed42_d14.md` violaciones 0; 317 passed |
| R2-B7-01 | DEPLOY_VPS.md | B7 | ✅ | ce0adda | cita el run `37247682028` |
| R2-B7-02 | GO_LIVE.md | B7 | ✅ | ce0adda | checklist del dueño, identidad sin inventar |
| R2-B7-03 | RUNBOOK.md | B7 | ✅ | ce0adda | cita el mismo run |

## Evidencia ya pegada en esta sesión

- B. `python main.py --mode prompts`, `--mode demo` y `--mode status`: exit 0. Demo: 3 leads, 1 en `revision` (alto valor), 2 en `pitch_listo`, fallback `sin_key`, sin envío real.
- C. `apps/web`: oxlint 0, vitest 8 passed, `vite build` ok, Playwright 3 passed. `apps/site`: `astro build` ok, node:test 7 passed. El sitio no tiene suite Playwright propia; el e2e del dashboard levanta el sitio.
- E. Compose v5.6.0: `config --quiet` exit 0. Servicios: db, migrate, api, backup, caddy, worker. Prod sin `SECRET_KEY`: `ProdConfigError` / `APP_MODE=prod no arranca: falta SECRET_KEY`.
- G. `pip-audit -r requirements.txt`: No known vulnerabilities found. `npm audit --omit=dev` en `apps/web` y `apps/site`: 0 altas, 0 críticas. El escaneo de secretos entra en la suite del motor.

## Bloqueos

`docker` no está instalado en el PATH de esta máquina. No se afirma un `docker compose up` local.

## Suite del motor

`cd engine && ruff check . && ruff format --check . && mypy . && pytest -q --cov --cov-fail-under=85`

- ruff check: All checks passed
- ruff format: 150 files already formatted
- mypy: Success: no issues found in 105 source files
- pytest: 317 passed, 1 warning, 5753.35s. `Required test coverage of 85% reached. Total coverage: 91.49%`

## Próxima acción exacta

Empujar `grok/deploy-r2-041026`, esperar el run de CI (engine, e2e, compose-smoke) y recién entonces escribir `docs/INFORME_FINAL_R2.md` y abrir el PR a `main`. No marcar D, G21, H ni I hasta ese run verde.
