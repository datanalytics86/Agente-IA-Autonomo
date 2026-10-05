# Infra

Demo y CI no envían correo ni cobran: `APP_MODE=demo`, `DRY_RUN=true`, `OUTREACH_ENABLED=false` salen de `infra/.env.ci` o del `.env` de la raíz. Sin Docker este directorio no se puede verificar en local.

## Levantar

Desde la raíz del repo. Si no hay `.env`, el archivo de prueba cubre la sustitución y el `env_file`:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.ci up -d --build --wait
python infra/scripts/smoke.py
```

`env_file` de api, worker y migrate: `../.env` y, si no está, `infra/.env.ci`. El de la raíz pisa al de CI. `DATABASE_URL` del contenedor se arma con el driver `postgresql+psycopg://` hacia el servicio `db`. Una clave con `@`, `:`, `/` o `#` tiene que ir ya codificada.

- `http://127.0.0.1/` es el build de `apps/site` (dentro de la imagen, no `infra/site-root`). El panel no está en esa raíz.
- `http://127.0.0.1/admin/` es el dashboard. Vite usa `base: '/admin/'` y el router `basepath: '/admin'`. `/admin` redirige a `/admin/` (308).
- `/api`, `/webhooks`, `/demo` y `/u` van a `api:8000`. `/healthz` y `/readyz` también: JSON `{"status":"ok"}`, no el HTML del sitio. `/readyz` sin base responde 503.
- `/demo` lleva `X-Robots-Tag: noindex, nofollow`.
- `migrate` corre `alembic upgrade head` y se queda vivo: un contenedor que sale, aunque sea con 0, `up --wait` lo toma por un fallo. El healthcheck es el archivo `/tmp/migrated`.
- El worker no sirve HTTP. El healthcheck de la imagen pegaría a `/healthz`; Compose lo reemplaza por el archivo `/tmp/worker-ready`, que `worker_entry.py` escribe después del primer `job_runs`.
- Postgres 16 en el compose base solo escucha en `127.0.0.1:5432`. En el override de prod no publica puertos.

Volúmenes: `pgdata`, `artifacts` (`/app/output` en api y worker), `client_sites`, `caddy_data`, `backups`.

## Producción

Hace falta un `.env` real en la raíz. `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` y `SITE_DOMAIN` no tienen default: si faltan, Compose no arranca. El Caddy de prod es `infra/Caddyfile.prod` (TLS y `on_demand_tls` contra `http://api:8000/api/internal/domain-check`). Los sitios de clientes se leen de `client_sites/<host>`.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env config
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

Ese es el arranque de producción. Caddy publica 80 (el archivo base) y 443 (el override) y usa `infra/Caddyfile.prod`. El panel queda en `https://<SITE_DOMAIN>/admin/`. `GET /healthz` es el JSON de la API. El worker sigue sin HTTP. Paso a paso del VPS: `docs/DEPLOY_VPS.md`.

No inventar nombre, RUT ni dirección de la agencia en ese `.env`.

## Backup

El servicio `backup` hace `pg_dump` al arrancar y cada 24 h, y borra dumps de más de 14 días (también deja como máximo 14 archivos). `restore.sh` carga el dump en una base temporal, lee `alembic_version` y la borra. El smoke lo llama así:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.ci exec -T backup /usr/local/bin/restore.sh /backups/<dump>
```

`backup.ps1` y `restore.ps1` son la misma operación en el host, si `pg_dump` está instalado. No los corras contra una base que no sea de prueba.

## Smoke

`infra/scripts/smoke.py` cubre los 10 pasos de la §7.2 contra el compose base y `infra/.env.ci`. En CI lo corre el job `compose-smoke`. La corrida verde del código de producto `21593a9` es https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37259799699. La corrida anterior, sobre `00190b0`, es https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37247682028. `POST /api/public/diagnostico` está implementado como 202; el script acepta 200 o 202 y comprueba que el lead quede en `/api/leads`.
