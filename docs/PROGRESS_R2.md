# PROGRESS — Ronda 2 deploy 04-10-2026

Rama: `grok/deploy-r2-041026` · Base: `main` en `d5dcc6b` (incluye el merge del PR #1) · Auditoría de partida: `cb347d0` · Ola actual: 0

## Estado de la DoD (§8)

A ☐ · B ☐ · C ☐ · D ☐ · E ☐ · F ☐ · G ☐ · H ☐ · I ☐

Docker local: el comando `docker` no existe en esta máquina. La evidencia del smoke (§7.2) tiene que salir del job `compose-smoke` en GitHub Actions.

## Línea base

`cd engine` y `pytest -q --cov=core --cov=agents --cov=worker --cov-fail-under=80` el 2026-10-04: **271 passed**, cobertura **86.15 %**, `PYTEST=0`, 97.56 s. `docker version` no es un comando en esta máquina.

## Hallazgos G1–G24

| ID | Severidad | Estado | Tarea |
|----|-----------|--------|-------|
| G1 | P0 | ☐ | R2-B1-01 driver Postgres y requirements |
| G2 | P0 | ☐ | R2-B1-03 R2-B1-05 sitio Astro en Caddy |
| G3 | P0 | ☐ | R2-B5-02 R2-B1-03 `/admin` |
| G4 | P0 | ☐ | R2-B1-04 R2-B1-05 TLS y volúmenes |
| G5 | P0 | ☐ | R2-B1-04 `env_file` |
| G6 | P0 | ☐ | R2-B5-01 fail-fast |
| G7 | P0 | ☐ | R2-B1-04 Alembic al arrancar |
| G8 | P0 | ☐ | R2-B1-02 R2-B1-07 imagen y smoke CI |
| G9 | P0 | ☐ | R2-B2-01 a R2-B2-04 wiring |
| G10 | P0 | ☐ | R2-B3-01 a R2-B3-03 pipeline único |
| G11 | P0 | ☐ | R2-B3-04 R2-B3-06 entrega |
| G12 | P0 | ☐ | R2-B4-01 R2-B2-03 inbound |
| G13 | P0 | ☐ | R2-B2-05 Mercado Pago |
| G14 | P0 | ☐ | R2-B4-02 R2-B4-03 webhooks |
| G15 | P0 | ☐ | R2-B4-04 informe de diagnóstico |
| G16 | P0 | ☐ | R2-B3-05 saldo |
| G17 | P1 | ☐ | R2-B5-03 Turnstile |
| G18 | P1 | ☐ | R2-B2-04 notifier |
| G19 | P1 | ☐ | R2-B6-01 mypy |
| G20 | P1 | ☐ | R2-B6-02 cobertura |
| G21 | P1 | ☐ | R2-B6-03 CI |
| G22 | P1 | ☐ | R2-B6-04 simulación real |
| G23 | P1 | ☐ | R2-B1-06 backups |
| G24 | P1 | ⏳ | R2-B0-01 nota en los docs de la ronda 1 |

## Tablero

| ID | Tarea | Agente | Estado | Commit | Evidencia |
|----|-------|--------|--------|--------|-----------|
| R2-B0-00 | Rama y contratos | B0 | ⏳ | | esta ola |
| R2-B0-01 | Nota en docs de la ronda 1 | B0 | ⏳ | | G24 |
| R2-B0-02 | `.env.example` e `infra/.env.ci` | B0 | ☐ | | |
| R2-B0-03 | Informe y PR | B0 | ☐ | | `docs/INFORME_FINAL_R2.md` |
| R2-B1-01 | psycopg y requirements | B1 | ☐ | | G1 |
| R2-B1-02 | Dockerfile.engine | B1 | ☐ | | G8 |
| R2-B1-03 | Dockerfile.front | B1 | ☐ | | G2 G3 |
| R2-B1-04 | Compose base y prod | B1 | ☐ | | G4 G5 G7 |
| R2-B1-05 | Caddyfile | B1 | ☐ | | G2 G4 |
| R2-B1-06 | Backup y restauración | B1 | ☐ | | G23 |
| R2-B1-07 | smoke.py y job CI | B1 | ☐ | | G8 |
| R2-B2-01 | `build_ports` | B2 | ☐ | | G9 |
| R2-B2-02 | SMTP con candado | B2 | ☐ | | G9 |
| R2-B2-03 | IMAP sin intención | B2 | ☐ | | G9 G12 |
| R2-B2-04 | Resto de adaptadores y notifier | B2 | ☐ | | G9 G18 |
| R2-B2-05 | `build_payments` en la API | B2 | ☐ | | G13 |
| R2-B2-06 | Estado de canales | B2 | ☐ | | |
| R2-B3-01 | Funnel invoca agentes | B3 | ☐ | | G10 |
| R2-B3-02 | Artefactos en disco | B3 | ☐ | | G10 |
| R2-B3-03 | Pitch del Diagnoser | B3 | ☐ | | G10 |
| R2-B3-04 | Entrega con aprobación | B3 | ☐ | | G11 |
| R2-B3-05 | Saldo | B3 | ☐ | | G16 |
| R2-B3-06 | Publicación | B3 | ☐ | | G11 |
| R2-B4-01 | Clasificar inbound con Mobile | B4 | ☐ | | G12 |
| R2-B4-02 | Webhook de correo | B4 | ☐ | | G14 |
| R2-B4-03 | Webhook de Meta | B4 | ☐ | | G14 |
| R2-B4-04 | Informe de diagnóstico | B4 | ☐ | | G15 |
| R2-B5-01 | Fail-fast de prod | B5 | ☐ | | G6 |
| R2-B5-02 | Base `/admin` | B5 | ☐ | | G3 |
| R2-B5-03 | Turnstile en el sitio | B5 | ☐ | | G17 |
| R2-B5-04 | Identidad en el build del sitio | B5 | ☐ | | G6 |
| R2-B6-01 | mypy del motor | B6 | ☐ | | G19 |
| R2-B6-02 | Cobertura 85 % | B6 | ☐ | | G20 |
| R2-B6-03 | CI openapi y e2e | B6 | ☐ | | G21 |
| R2-B6-04 | Simulación del pipeline real | B6 | ☐ | | G22 |
| R2-B7-01 | DEPLOY_VPS.md | B7 | ☐ | | |
| R2-B7-02 | GO_LIVE.md | B7 | ☐ | | |
| R2-B7-03 | RUNBOOK.md | B7 | ☐ | | |

## Bloqueos

`docker` no está instalado en el PATH de esta máquina. No se afirma un healthz local.

## Próxima acción exacta

Pegar la línea base de pytest y lanzar la ola 1: B1, B2, B5 y B6 en paralelo.
