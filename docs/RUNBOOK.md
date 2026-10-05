# Runbook

Operación local y de producción. Los defaults dejan el sistema en demo: no envía, no cobra y no manda mensajes directos. Instagram y LinkedIn en frío quedan en la bandeja manual. WhatsApp no se usa en frío.

El panel no está en la raíz del sitio. Vite publica con `base: '/admin/'` y el router usa `basepath: '/admin'`. En producción se abre `https://<SITE_DOMAIN>/admin/`. Caddy redirige `/admin` a `/admin/` (308).

La evidencia del stack de demo es el job `compose-smoke` de CI: https://github.com/datanalytics86/Agente-IA-Autonomo/actions/runs/37247682028 sobre el commit `00190b0`. En esta máquina no está el comando `docker`.

## Pausar la salida

El interruptor es la clave `kill_switch` de `settings_kv`, no una variable de entorno.

- `false` es detenido. Es el default cuando la clave no existe.
- `true` es armado. Recién ahí el job `outreach_send` puede intentar un envío.

En el panel: el botón del kill switch, o `https://<SITE_DOMAIN>/admin/config` (`PUT /api/settings`). Con el interruptor en false el worker anota `kill switch detenido; no se envía` y no manda la cola de outreach.

El interruptor no detiene el inbound (`inbound_poll`, cada 5 minutos) ni los jobs de cumplimiento (`data_requests_watch`, `data_retention`, `demo_expiry`, digest HITL, `metrics_rollup`, el tick del pipeline). Siguen corriendo.

## Cuándo sale un correo de verdad

Hacen falta las cuatro cosas a la vez:

1. `APP_MODE=prod`
2. `OUTREACH_ENABLED=true`
3. `kill_switch` en true
4. credencial del canal (SMTP: host, usuario, clave, usuario IMAP, `OUTREACH_FROM` y `PUBLIC_BASE_URL`)

`DRY_RUN=true` es un candado aparte. Bloquea el socket aunque las cuatro pasen: el adaptador devuelve `blocked` con razón `dry_run` y no abre SMTP. También frena el correo transaccional. La imagen del motor trae `DRY_RUN=true`; en el VPS lo pisa el `.env`.

Instagram y LinkedIn en frío no usan ese candado: el worker los deja en `manual_pending`. Se copian a mano en `https://<SITE_DOMAIN>/admin/manual`. El navegador no los envía. WhatsApp nunca en frío, ni por el worker ni desde esa bandeja.

## Revisar HITL

`https://<SITE_DOMAIN>/admin/hitl`. No sirve buscar la bandeja en `https://<SITE_DOMAIN>/`.

La bandeja lista aprobaciones `pending`. Aprobar, rechazar o editar llama a la API (`/api/approvals/...`). Aprobar no marca el lead como enviado en el cliente: el motor retoma la etapa que estaba en pausa. Un deal de 2.800.000 CLP o más (`HITL_VALUE_CLP`) va a revisión antes de un envío o una propuesta. No bajar ese umbral ni la tasa `HITL_RESPONSE_RATE` (0.12).

Otras rutas del mismo panel: `/admin/manual` (bandeja manual), `/admin/leads`, `/admin/compliance`, `/admin/agentes` (cada canal en `real`, `dry_run` o `deshabilitado: falta X`), `/admin/logs`, `/admin/config`.

El login es `POST /api/auth/login` contra la tabla `users`. La cookie `session` es HttpOnly. Las escrituras llevan el header `X-CSRF-Token`. Cinco intentos fallidos en 15 minutos responden 429.

## Solicitudes de derechos

El formulario público es `POST /api/public/derechos`. Tipos que acepta el motor: `acceso`, `rectificacion`, `supresion`, `oposicion`, `portabilidad`, `bloqueo`. El plazo queda a 30 días.

Se responden en `https://<SITE_DOMAIN>/admin/compliance`. Ahí está el correo de quien pidió, el detalle y el vencimiento. El estado pasa a `open`, `done` o `rejected` (`PATCH /api/compliance/data-requests`). La lista de supresión muestra el hash, no el valor en claro. Se puede agregar o borrar una supresión en la misma pantalla (`email`, `domain`, `instagram`, `linkedin`, `phone`).

Todos los días a las 09:00 (`America/Santiago`) `data_requests_watch` avisa si una solicitud abierta vence en menos de 3 días. El kill switch no para ese job.

## Rotar claves

`SECRET_KEY` firma la cookie de sesión (sal `agencia-session`, 7 días) y el token de baja (sal `baja`). Cambiarla invalida las sesiones ya emitidas: el login vuelve a pedir clave y los links de baja viejos dejan de verificar. La nueva clave tiene que tener al menos 32 caracteres. No imprimirla.

En el VPS: editar `SECRET_KEY` en el `.env` de la raíz y volver a crear los contenedores con el mismo arranque.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

La clave del admin no es `ADMIN_PASSWORD_HASH`. Esa variable solo la exige el fail-fast. La clave que compara el login está en `users.password_hash`. Para rotarla, volver a correr `create-admin` dentro del contenedor. Imprime `admin actualizado: <correo>` y no imprime la clave. `ADMIN_PASSWORD` es la clave en claro solo de ese comando.

```bash
read -r -s ADMIN_PASSWORD
export ADMIN_PASSWORD
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T -e ADMIN_PASSWORD api python main.py --mode create-admin
unset ADMIN_PASSWORD
```

El fail-fast solo mira que `ADMIN_PASSWORD_HASH` no esté vacía. No la compara con la clave nueva: el login lee `users.password_hash`, que acaba de reescribir `create-admin`. Un hash viejo, si no está vacío, no tumba el arranque. Conviene regenerarlo para no dejar en el `.env` la clave anterior. Desde `engine/` con el venv: `python -c "from api.security import hash_password; print(hash_password('la-clave'))"`.

## Restaurar un backup

El servicio `backup` hace `pg_dump` al arrancar y cada 24 h, y deja como máximo 14 dumps en `/backups` (`agencia-<fecha UTC>.dump`).

`restore.sh` carga el dump en una base temporal (`restore_<timestamp>`), lee `alembic_version` y borra esa base. No toca la base de trabajo. Imprime `restauracion ok: restore_…` y sale 0 solo si la tabla responde.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T backup ls -1t /backups
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T backup /usr/local/bin/restore.sh /backups/agencia-YYYYMMDDTHHMMSSZ.dump
```

No hay un comando de downgrade de Alembic en el repo. No improvisar uno. Volver el código a un commit anterior está en `docs/DEPLOY_VPS.md` y no revierte el esquema ya aplicado.

`backup.ps1` y `restore.ps1` repiten la operación en el host si `pg_dump` está instalado. No correrlos contra una base que no sea de prueba.

## Logs

Desde la raíz del clon, con los dos archivos de Compose. Si no, Compose no apunta al proyecto de prod.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env logs --tail 200 api worker
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env logs -f api
```

El worker no sirve HTTP: no tiene `/healthz`. Su healthcheck es el archivo `/tmp/worker-ready`. `GET /healthz` en el sitio es JSON `{"status":"ok"}` de la API. `GET /readyz` es el mismo JSON si la base responde; si no, 503.

En el panel, `https://<SITE_DOMAIN>/admin/logs` lee `GET /api/events`.

## Arranque en demo

PowerShell, desde la raíz del repositorio:

```powershell
cd engine
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe main.py --mode demo
.\.venv\Scripts\python.exe main.py --mode status
```

Bash:

```bash
cd engine
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python main.py --mode demo
.venv/bin/python main.py --mode status
```

`SECRET_KEY` vacío en demo usa un valor efímero del proceso. No se imprime la clave.

API local:

```powershell
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = "<definir en el entorno, no en el repo>"
.\.venv\Scripts\python.exe main.py --mode create-admin
$env:API_HOST = "127.0.0.1"
$env:API_PORT = "8000"
.\.venv\Scripts\python.exe main.py --mode api
```

Worker local, un solo proceso. El lock vive en la base.

```powershell
.\.venv\Scripts\python.exe main.py --mode worker
```

## Simulación

No usa red. La misma semilla y los mismos días reescriben el mismo reporte.

```powershell
.\.venv\Scripts\python.exe main.py --mode simulate --days 14 --seed 42
```

El reporte queda en `docs/simulacion/reporte_seed42_d14.md`. En CI corre `--days 3`.

## Sitio y dashboard en local

```powershell
cd apps\site
npm ci
npm run build
npm test
cd ..\web
npm ci
npm run lint
npm test
npm run build
npm run e2e
```

El e2e levanta la API en `127.0.0.1:8765` y el sitio en `127.0.0.1:4321`, con base sqlite desechable. No cobra: el checkout falso dice que no hubo cobro y el webhook local marca el pago. El dev del panel escucha en el puerto 8080; en Compose el panel es `/admin/`.

## Base de datos local

SQLite por defecto: `engine/state/agencia.db` (no se versiona). Postgres 16 en Compose.

```powershell
.\.venv\Scripts\python.exe main.py --mode migrate-json
```

Ese modo copia el JSON legado, no lo reescribe, y se puede correr dos veces. Un JSON corrupto sale con código 1 y no crea la base.

El compose de demo y de CI es solo el archivo base, con `infra/.env.ci`:

```bash
docker compose -f infra/docker-compose.yml --env-file infra/.env.ci up -d --build --wait
```

No usar ese comando en el VPS.

## Cuando algo sale mal

| Síntoma | Qué mirar |
|---|---|
| No salen correos | Esperado si falta cualquiera de las cuatro condiciones, o si `DRY_RUN=true`. Instagram y LinkedIn en frío están en la bandeja manual. WhatsApp no se manda en frío. |
| El proceso muere al arrancar en prod | El log dice `APP_MODE=prod no arranca:` y el hueco (`falta SECRET_KEY`, clave corta, `falta DATABASE_URL`, `falta ADMIN_EMAIL`, `falta ADMIN_PASSWORD_HASH`, `falta PUBLIC_BASE_URL`, URL sin https, `falta AGENCY_NAME`, `falta AGENCY_EMAIL`). |
| Compose ni siquiera crea los contenedores | Falta `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` o `SITE_DOMAIN`. En prod no tienen default. |
| Login 429 | Cinco intentos fallidos en 15 minutos. Esperar. |
| Webhook 401 | Firma o secreto. Mercado Pago no confía en el cuerpo: consulta el pago. |
| `/demo/<token>` 410 | La pieza venció (`DEMO_TTL_DAYS`, 30). |
| Dos workers | El segundo no toma el lock. Dejar uno. |
| Alto valor en revisión | Umbral 2.800.000 CLP. No se envía solo. No bajarlo. |
| `/admin` da 404 y la raíz sí carga | Falta la barra, o se está mirando un build viejo sin `base: '/admin/'`. La URL es `/admin/`. |

## Producción

Seguir `docs/GO_LIVE.md` y `docs/DEPLOY_VPS.md`. No completar nombre, RUT ni dirección en el código: van por entorno cuando el dueño los tenga. La revisión del abogado sigue pendiente.
