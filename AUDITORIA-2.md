# Auditoría 2

Revisión del HEAD de `main` en `657d158` (13 de noviembre de 2026). No es un dictamen legal y no habilita envíos ni cobros reales. Los arreglos viven en PRs aparte y no están en este commit.

## Cómo se miró

- Lectura de API, worker, Compose, Caddy y el sitio.
- `npm audit` en `apps/web` y `apps/site` (con y sin `--omit=dev`).
- `pip-audit` 2.10.1 sobre `engine/requirements.txt` y `engine/requirements-dev.txt`.
- `gitleaks` 8.28.0 sobre los 75 commits del historial (`gitleaks detect`, no `--no-git`). No se reescribió la historia.

## Resumen

| Severidad | Hallazgo | Dónde | Estado en esta ronda |
|---|---|---|---|
| Alta | El esquema de producción se crea con `create_all()`, no con Alembic | `engine/api/app.py:27`, `engine/worker/cli.py:15`, `engine/api/cli.py:44` | Abierto |
| Alta | El worker de producción diagnostica con un texto fijo y avanza de estado aunque no exista el archivo | `engine/worker/funnel.py:214`, `engine/worker/funnel.py:263` | Abierto |
| Alta | El rate limit del login no usaba la IP real detrás de Caddy | `engine/api/routers/auth.py:16` | PR #32 |
| Alta | `/api/internal/domain-check` quedaba en el proxy público de `/api` | `infra/Caddyfile:29` | PR #33 |
| Alta | `engine/output` no tiene volumen y el backup no lo incluye | `infra/docker-compose.yml:34` | PR #27 |
| Alta | No hay prueba de restore del dump de Postgres | `infra/scripts/backup.sh:1` | PR #31 |
| Media | Falta `Strict-Transport-Security` en los sitios TLS | `infra/Caddyfile:9` | PR #28 |
| Media | Nav y CTA de la landing miden menos de 44 px a 360 px | `apps/site/src/components/Header.astro:28`, `apps/site/src/pages/index.astro:39`, `apps/site/src/pages/index.astro:90` | PR #29 |
| Media | Logs JSON solo en el logger `api`. Worker y `core` salen en texto | `engine/api/log.py:26` | Abierto |
| Media | La imagen y el servicio `api` no tienen healthcheck, aunque `/healthz` y `/readyz` existen | `infra/Dockerfile.engine:41`, `engine/api/routers/health.py:18`, `engine/api/routers/health.py:23` | Abierto |
| Media | En `APP_MODE=prod` solo se exige `SECRET_KEY`. No se exigen HTTPS, Postgres ni identidad | `engine/core/config.py:187` | Abierto |
| Media | El checkout público no pasa por honeypot ni Turnstile | `engine/api/routers/public.py:108` | Abierto |
| Media | El digest del worker no sale de `LogNotifier` | `engine/worker/defaults.py:305` | Abierto |
| Media | mypy estricto no cubre `api/`, `agents/`, `integrations/` | `engine/pyproject.toml:80` | Abierto |
| Baja | Cinco avisos high de `vite` y uno de `nanoid`, solo en devDependencies | `apps/web/package.json:39` | PR #30 |
| Baja | Starlette avisa que `httpx` con `TestClient` está deprecado | `engine/tests/test_api_http.py:15` | Abierto |
| Baja | gitleaks marca `infra/.env.ci` en el commit `589a37a` | historial, no el árbol | PR #25 |
| Baja | El 500 incluye el nombre de la clase de la excepción | `engine/api/errors.py:111` | Abierto |
| Baja | El rate limit de login vive en memoria del proceso | `engine/api/security.py:32` | Abierto |

## Seguridad

`/healthz` responde `{"status":"ok"}` sin tocar la base (`engine/api/routers/health.py:18`). `/readyz` ejecuta `SELECT 1` y responde 503 si la base no responde (`engine/api/routers/health.py:23`). Caddy ya manda esas rutas a la API (`infra/Caddyfile:18`).

La sesión es HttpOnly y el CSRF va en las escrituras del admin (`engine/api/deps.py:160`, `engine/api/routers/admin.py:70`). `APP_MODE=prod` rechaza `SECRET_KEY` de menos de 32 caracteres (`engine/core/config.py:187`) y oculta `/docs`. Las firmas de webhooks vacías se rechazan (`engine/api/security.py:207`).

En `657d158` el login limitaba por email, no por IP (`engine/api/routers/auth.py:16`). Detrás de Caddy el par TCP es el proxy, y un `X-Forwarded-For` directo era falsificable si alguien lo hubiera usado. El PR #32 lee el header solo cuando el par está en `FORWARDED_ALLOW_IPS` y arranca uvicorn con `--proxy-headers` y esa lista. En Compose, Caddy queda en `172.30.210.10`.

`/api/internal/domain-check` aceptaba loopback o `INTERNAL_CHECK_TOKEN` (`engine/api/routers/internal.py:28`) pero el Caddyfile publicaba todo `/api` (`infra/Caddyfile:29`). El PR #33 responde 404 en el sitio público, deja la llamada interna de Caddy hacia `api:8000`, y limita por minuto. `X-Forwarded-For` no autoriza.

`GuardedOutreach` devuelve `blocked` también cuando el candado está abierto (`engine/worker/defaults.py:48`). El camino de producción, si hay SMTP, usa `_SmtpBridge` (`engine/worker/defaults.py:274`). El fallback de esa clase no envía.

## Dependencias

`pip-audit` sobre `engine/requirements.txt` y `engine/requirements-dev.txt`: sin vulnerabilidades conocidas.

`npm audit --omit=dev` en `apps/web` y `apps/site`: 0. `apps/site` completo: 0.

`npm audit` de `apps/web` en `657d158` (todo en devDependencies):

| Paquete | Rango | Aviso |
|---|---|---|
| vite | 8.0.0–8.1.5 | GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm (launch-editor), GHSA-9jrq-w75r-8gcw, GHSA-rq7h-c2jc-7f22 |
| nanoid | &lt; 3.3.18 | GHSA-2v37-7h3g-55p8 |

QA había nombrado también `openapi-typescript`. En este HEAD (`^7.13.0`, `apps/web/package.json:35`) no aparece en el audit. El PR #30 sube el lock a vite 8.3.8 y nanoid 3.3.20. `npm audit` del árbol completo queda en cero. No cambia código de producción.

Starlette 1.10, al importar `TestClient` sin `httpx2`, emite: `Using httpx with starlette.testclient is deprecated; install httpx2 instead` (`engine/tests/test_api_http.py:15`, origen en `starlette/testclient.py:41`). Es un aviso de tests. No se cambió el cliente en esta ronda para no mover la suite a otro paquete.

## Secretos

`gitleaks` sobre el historial encontró tres `generic-api-key`. Ninguno está en el árbol actual.

1. `infra/.env.ci:13` en `589a37a09e43ab997999e543eab044fadb11a929`. El archivo dice que son valores de prueba. Lo marcado es `SECRET_KEY=ci-secret-key-de-prueba-no-es-prod-32`. Al lado están `POSTGRES_PASSWORD=agencia-ci` y `ADMIN_PASSWORD=clave-de-prueba`, que la regla no marcó. Son dummy. El archivo ya no existe en `main`. El PR #25 deja `.gitleaks.toml` que solo ignora ese valor si coinciden la ruta, ese commit y el secreto. No se reescribió la historia.
2. `engine/tests/test_config.py` en `49c46f9`: `SECRET_KEY=raiz-secret-key-de-produccion-32` dentro de un test que escribe un `.env` temporal. El archivo actual usa `"x" * 32`. Sigue en el historial. No entra en el allowlist.
3. `engine/tests/test_payments.py:73` en `ec401614`: `secret="mp-secret"` en un test de firma. Dummy. No entra en el allowlist.

Un `gitleaks detect` con el config nuevo reporta 2, no 3. Sin el config, siguen siendo 3.

## Readiness de producción

La configuración sale de pydantic-settings, con `engine/.env` y luego el `.env` de la raíz (`engine/core/config.py:48`). Los ejemplos no traen `ADMIN_PASSWORD`.

Alembic tiene una revisión (`engine/migrations/versions/2fb1d83b32e1_esquema_inicial.py`) y `env.py` lee `DATABASE_URL`. El arranque de la API, del worker y de `create-admin` llama `Base.metadata.create_all()`. Una migración futura no se aplica sola.

Los logs de la API son JSON en el logger `api` (`engine/api/log.py:12`). El worker no llama `configure_logging`.

Compose de demo no monta `engine/output`. El PR #27 agrega el volumen nombrado `engine_output` en `infra/docker-compose.prod.yml` y lo mete en el archivo que escribe `backup.sh` cuando `ENGINE_OUTPUT_DIR` está definido. El PR #31 prueba dump y restore contra Postgres 16 en GitHub Actions.

No hay workflow de deploy activo. El PR #26 agrega uno con `workflow_dispatch` y `if: false`. Haría falta un VPS con Docker y, como secretos de GitHub, `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY` y `DEPLOY_PATH`. El `.env` de la app se queda en ese host.

## Deuda que queda abierta

- El pipeline programado no llama a los agentes de `engine/agents/`. `_diagnose` escribe un markdown fijo (`engine/worker/funnel.py:236`) y el estado igual avanza si el HTML no está en disco (`engine/worker/funnel.py:263`).
- `LogNotifier.send_digest` no envía (`engine/worker/defaults.py:85`).
- El checkout público no usa el mismo `_gate` que diagnóstico y contacto (`engine/api/routers/public.py:108`).
- El 500 devuelve `type` con el nombre de la excepción (`engine/api/errors.py:111`).
- El rate limit sigue en un dict del proceso. Varios workers no comparten el conteo.
- No hay `HEALTHCHECK` en `infra/Dockerfile.engine`. Las rutas HTTP sí existen.
- `httpx2` para callar el aviso de Starlette.
- Los dos hallazgos históricos de gitleaks en tests, a propósito fuera del allowlist.

## PRs de esta ronda

Ninguno se mergea desde aquí.

| PR | Tema |
|---|---|
| #25 | Allowlist de gitleaks para `infra/.env.ci` |
| #26 | Workflow de deploy desactivado |
| #27 | Volumen `engine_output` y backup |
| #28 | HSTS en el sitio TLS |
| #29 | Área táctil de 44 px |
| #30 | vite 8.3.8 y nanoid 3.3.20 |
| #31 | Restore de Postgres en CI |
| #32 | IP real en el rate limit de login |
| #33 | `domain-check` interno y con límite |
