# Informe final — deploy 04-10-2026

Rama `grok/deploy-r2-041026`. Integrador B0. Base `main` en `d5dcc6b`. El SHA de producto es `21593a99ad6f48a0d5d1f02e2847148f6f54ef1f`. Este informe no cambia el motor ni las imágenes.

CI de ese SHA, seis jobs en success: https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37259799699

`docker` no está en el PATH de esta máquina. No hubo `docker compose up` local. El smoke §7.2 es el job `compose-smoke` de ese run.

Identidad pública: `[datos de la agencia]`. La revisión legal sigue pendiente (`docs/GO_LIVE.md`, `docs/compliance/REVISION_LEGAL.md`). No hay envío, cobro ni publicación reales.

## A. Motor

En `engine/`, con el venv y `PYTHONPATH=.`:

```
ruff check .
ruff format --check .
mypy .
pytest -q --cov --cov-fail-under=85
```

```
All checks passed!
150 files already formatted
Success: no issues found in 105 source files
317 passed, 1 warning in 5753.35s (1:35:53)
Required test coverage of 85% reached. Total coverage: 91.49%
```

Ese `--cov` pelado incluye los tests en la tabla. Sin el test de 14 días, los paquetes de fuente quedan en 89 %: `316 passed`, 1 deseleccionado, 9215 stmts, 1049 miss. Pisos: `services.py` 96 %, `security.py` 82 %, `wiring.py` 92 %, `closer.py` 100 %, `delivery.py` 100 %.

El job `engine` de CI no usa ese comando. Usa `--cov=core --cov=agents --cov=worker --cov-fail-under=80` y después `python main.py --mode simulate --days 3 --seed 42`. En el run `37259799699` salió:

```
TOTAL                      3846    420    89%
Required test coverage of 80% reached. Total coverage: 89.08%
317 passed, 1 warning in 3656.14s (1:00:56)
```

`agents/delivery.py` quedó en 100 % en esa tabla. El job terminó en success, así que la simulación de 3 días salió 0. En el log aparece el aviso de demo `SECRET_KEY vacío en demo: se usa un valor efímero de este proceso, no persistido`.

## B. Compatibilidad

`python main.py --mode prompts`, `--mode demo` y `--mode status` salen 0. El demo deja 3 leads (2 en `pitch_listo`, 1 en `revision` por alto valor, Clínica Dental El Roble a 2.800.000), fallback `sin_key`, cola manual de LinkedIn y ningún envío real.

## C. Front

`apps/web`: oxlint `Found 0 warnings and 0 errors`, vitest `Tests  8 passed (8)`, `npm run build` exit 0. Playwright local: `3 passed (1.1m)`. En el run de CI, el job `e2e`: `3 passed (9.5s)`.

`apps/site` no tiene suite Playwright. El job `e2e` construye el sitio Astro y lo levanta en `:4321`. `astro build` exit 0 y `npm test`: `# tests 7`, exit 0. El job `site` del run quedó en success.

## D. Docker

Job `compose-smoke` del run `37259799699`, conclusion success, sobre `21593a9`. `infra/scripts/smoke.py` contra el compose base con `infra/.env.ci`:

```
1 healthz y readyz ok
2 sitio Astro ok
3 dashboard /admin ok
4 login y /api/leads ok
5 diagnostico 200 lead 2a83bfab5e25473a9cdd9f169dba1e29
6 demo noindex ok
7 alembic head 2fb1d83b32e1
8 job_runs=1
9 datos persisten tras restart
10 backup y restauracion /backups/agencia-20261005T033339Z.dump
smoke ok
```

El run anterior https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37247682028 (commit `00190b0`) no es el smoke de este HEAD: el worker cambió después.

## E. Prod config

Compose v5.6.0, sin daemon: `docker-compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config --quiet` exit 0. Servicios: db, migrate, api, backup, caddy, worker. El `.env` temporal de esa validación se borró.

Arranque en prod sin `SECRET_KEY`:

```
ProdConfigError
APP_MODE=prod no arranca: falta SECRET_KEY
```

## F. Autonomía

`docs/simulacion/reporte_seed42_d14.md`, seed 42, 14 días, pipeline real. La suite de 317 passed lo vuelve a ejercer. El archivo no se reescribió en esa corrida.

```
nuevo 89
pitch_listo 166
enviado 42
entregado 1
revision 1
perdido 1
opt_out 1
bounced 1
manual_pending 1
queued 50
received 4
sent 46
enviados 46
ingresos_clp 350000
canal_pausado email_outreach
llamadas_de_red 0
violaciones: 0
```

## G. Seguridad

`pip-audit` 2.10.1 sobre `engine/requirements.txt`: `No known vulnerabilities found`. `npm audit --omit=dev` en `apps/web` y `apps/site`: `found 0 vulnerabilities`, exit 0. `engine/tests/test_secret_scan.py::test_el_arbol_no_contiene_secretos` entra en los 317 passed.

## H. Docs

`docs/DEPLOY_VPS.md`, `docs/GO_LIVE.md`, `docs/RUNBOOK.md` y el README están en la rama y citan el smoke de `21593a9`. G1–G24 quedan cerrados en `docs/PROGRESS_R2.md` contra un commit o contra el run `37259799699`. La revisión del abogado no se marca hecha. El nombre, el RUT y la dirección siguen siendo `[datos de la agencia]` hasta que el dueño los ponga en el entorno.

## I. CI y PR

Los seis jobs del run `37259799699` están en success sobre `21593a9`: engine, web, site, openapi, e2e, compose-smoke. El PR hacia `main` sale de `grok/deploy-r2-041026` con este informe como cuerpo. El commit que agrega este archivo no cambia el motor ni las imágenes.
