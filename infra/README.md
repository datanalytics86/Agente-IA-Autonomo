# Infra

Demo y CI no envían correo ni cobran: `APP_MODE=demo`, `DRY_RUN=true`, `OUTREACH_ENABLED=false` salen de `infra/.env.ci` o del `.env` de la raíz. Sin Docker este directorio no se puede verificar en local.

## Levantar

Desde la raíz del repo. Si no hay `.env`, el archivo de prueba cubre la sustitución y el `env_file`:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.ci up -d --build --wait
python infra/scripts/smoke.py
```

`env_file` de api, worker y migrate: `../.env` y, si no está, `infra/.env.ci`. El de la raíz pisa al de CI. `DATABASE_URL` del contenedor se arma con el driver `postgresql+psycopg://` hacia el servicio `db`. Una clave con `@`, `:`, `/` o `#` tiene que ir ya codificada.

- `http://127.0.0.1/` es el build de `apps/site` (dentro de la imagen, no `infra/site-root`).
- `http://127.0.0.1/admin/` es el dashboard, construido con `base=/admin/`.
- `/api`, `/webhooks`, `/demo` y `/u` van a `api:8000`. `/healthz` y `/readyz` también: JSON, no el HTML del sitio.
- `/demo` lleva `X-Robots-Tag: noindex, nofollow`.
- `migrate` corre `alembic upgrade head` antes de api y worker. El contenedor queda vivo para que `up --wait` no lo tome por un fallo.
- Postgres 16 en el compose base solo escucha en `127.0.0.1:5432`. En el override de prod no publica puertos.

Volúmenes: `pgdata`, `artifacts` (`/app/output` en api y worker), `client_sites`, `caddy_data`, `backups`.

## Producción

Hace falta un `.env` real en la raíz. `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` y `SITE_DOMAIN` no tienen default: si faltan, Compose no arranca. El Caddy de prod es `infra/Caddyfile.prod` (TLS y `on_demand_tls` contra `http://api:8000/api/internal/domain-check`). Los sitios de clientes se leen de `client_sites/<host>`.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env config
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d
```

No inventar nombre, RUT ni dirección de la agencia en ese `.env`.

## Backup

El servicio `backup` hace `pg_dump` al arrancar y cada 24 h, y borra dumps de más de 14 días (también deja como máximo 14 archivos). `restore.sh` carga el dump en una base temporal, lee `alembic_version` y la borra. El smoke lo llama así:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.ci exec -T backup /usr/local/bin/restore.sh /backups/<dump>
```

`backup.ps1` y `restore.ps1` son la misma operación en el host, si `pg_dump` está instalado. No los corras contra una base que no sea de prueba.

## Smoke

`infra/scripts/smoke.py` cubre los 10 pasos de la §7.2. En CI lo corre el job `compose-smoke`. `POST /api/public/diagnostico` está implementado como 202; el script acepta 200 o 202 y comprueba que el lead quede en `/api/leads`.
