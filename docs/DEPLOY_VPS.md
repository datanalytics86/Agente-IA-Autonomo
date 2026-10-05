# Despliegue en un VPS

Ubuntu 22.04, 24.04 o 26.04, 64 bits. Los comandos de Compose se corren en la raíz del clon. El `.env` vive ahí y no se commitea (`.gitignore` ya ignora `.env`).

Este archivo no afirma que el smoke de Docker esté verde. La evidencia del stack de demo es el job `compose-smoke` de CI, y al escribir esto no hay una corrida verde del commit `922434a`.

## 1. Docker

Hace falta el plugin `docker compose` (v2), no el paquete viejo `docker-compose`. Guía de referencia: la de Docker Engine para Ubuntu, método del repositorio `apt`.

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

Para no usar `sudo` en cada comando: `sudo usermod -aG docker "$USER"` y volver a entrar en la sesión.

## 2. Firewall

Abrir SSH (el puerto que ya uses; casi siempre 22), 80 y 443. Caddy escucha 443 con TLS automático y usa el 80 para el reto HTTP de Let's Encrypt y la redirección. No abrir 5432.

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Los puertos que Compose publica (80 y 443) los salta Docker respecto de ufw. La regla que importa para la base es otra: en prod el servicio `db` no publica puertos (`ports: !reset []` en `infra/docker-compose.prod.yml`). Si el panel del proveedor también filtra, repetir ahí SSH, 80 y 443, y no abrir 5432.

## 3. DNS

Un registro A y, si el VPS tiene IPv6, un AAAA.

- `SITE_DOMAIN` apunta al VPS. Ese host sirve el sitio y el panel en `https://<SITE_DOMAIN>/admin/`. El dashboard no está en la raíz: Vite usa `base: '/admin/'` y el router `basepath: '/admin'`. Caddy redirige `/admin` a `/admin/` con 308.
- `ADMIN_DOMAIN` no es otro panel. En `infra/Caddyfile.prod` solo saca ese host del árbol de sitios de clientes. Si no se define, Compose usa `admin.invalid`. Si se define un host real, también lleva A y AAAA; un pedido a ese host responde 404, no el dashboard.

Los dominios de clientes no se cargan acá. Caddy pide el certificado on-demand y la API responde en `http://api:8000/api/internal/domain-check`. Esos sitios salen del volumen `client_sites`.

Esperar a que el A/AAAA resuelva al VPS antes del primer arranque: si no, el certificado del sitio falla.

## 4. Clonar

```bash
git clone https://github.com/datanalytics86/Agente-IA-Autonomo.git
cd Agente-IA-Autonomo
```

## 5. Armar el `.env`

```bash
cp .env.example .env
chmod 600 .env
```

Editar `.env` en el servidor. No commitearlo. No copiar `infra/.env.ci`: ese archivo es demo (`APP_MODE=demo`, `DRY_RUN=true`) y el override de prod no lo usa. `env_file` de api, worker y migrate apunta a `../.env` y es obligatorio.

La imagen del motor trae `APP_MODE=demo`, `DRY_RUN=true` y `OUTREACH_ENABLED=false`. El `.env` las pisa. En el VPS, `APP_MODE=prod`.

Compose, no la app, aborta si faltan estas cuatro. No tienen default en `infra/docker-compose.prod.yml`:

| Variable | Mensaje si falta |
|---|---|
| `POSTGRES_USER` | `POSTGRES_USER es obligatorio en prod` |
| `POSTGRES_PASSWORD` | `POSTGRES_PASSWORD es obligatorio en prod` |
| `POSTGRES_DB` | `POSTGRES_DB es obligatorio en prod` |
| `SITE_DOMAIN` | `SITE_DOMAIN es obligatorio en prod` |

`ADMIN_DOMAIN` sí tiene default (`admin.invalid`).

`DATABASE_URL` del `.env` de ejemplo es SQLite y sirve al CLI local. Dentro de api, worker y migrate, Compose la reemplaza por `postgresql+psycopg://<user>:<password>@db:5432/<db>`. Una clave con `@`, `:`, `/` o `#` hay que pasarla ya codificada: se interpola tal cual en esa URL y también es el valor que recibe Postgres.

`PUBLIC_BASE_URL` tiene que ser `https://` más el host. `http://` no alcanza.

`SECRET_KEY`: al menos 32 caracteres. Generarla, no reusar un ejemplo.

`ADMIN_PASSWORD_HASH`: hash argon2, no vacío. El login no compara contra esta variable (mira `users.password_hash`). El fail-fast de prod sí exige que esté definida. Desde `engine/`, con el venv ya instalado:

```bash
python -c "from api.security import hash_password; print(hash_password('la-clave'))"
```

En Windows, el intérprete del venv es `.\.venv\Scripts\python.exe`. Pegar la salida en `ADMIN_PASSWORD_HASH`. No pegar la clave en claro en el `.env`.

`AGENCY_NAME` y `AGENCY_EMAIL` son obligatorias para que el proceso arranque. No inventar nombre, RUT ni dirección. Si todavía no existen, el sitio público no se rellena con datos falsos: ver más abajo.

El resto de credenciales es opcional. Sin la de un canal, ese canal queda `deshabilitado: falta X` en `/api/agents` y en `https://<SITE_DOMAIN>/admin/agentes`. La lista de dónde sale cada una está en `docs/GO_LIVE.md`.

El HTML del sitio se hornea en la imagen (`infra/Dockerfile.front`). Ese Dockerfile solo pasa `PUBLIC_BASE_URL`. No pasa `AGENCY_*` ni `PUBLIC_TURNSTILE_SITE_KEY`. Con el compose de hoy, el sitio publicado muestra el marcador `[datos de la agencia]` aunque el `.env` del motor ya tenga nombre y correo. El motor sí lee `AGENCY_*` en runtime (correos y fail-fast).

## 6. Arranque

Desde la raíz del clon:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

Qué hace ese par de archivos:

- `db`: Postgres 16. Sin puertos publicados. El volumen es `pgdata`.
- `migrate`: `alembic upgrade head` y después no sale. Escribe `/tmp/migrated` y duerme. `up --wait` trata un contenedor que termina, aunque sea con 0, como fallo; por eso el proceso se queda vivo. Una segunda corrida del upgrade es idempotente.
- `api`: `python main.py --mode api`. El healthcheck de la imagen pide `http://127.0.0.1:8000/healthz` y exige JSON `{"status":"ok"}`, no HTML.
- `worker`: `python worker_entry.py`. No escucha HTTP. Deja un `job_runs` (`metrics_rollup`) y recién ahí crea `/tmp/worker-ready`. El healthcheck de Compose mira ese archivo. El de la imagen, que pega a `/healthz`, no aplica al worker: Compose lo reemplaza.
- `caddy`: `infra/Caddyfile.prod`. Publica 80 (el compose base) y 443 (el override). `/healthz` y `/readyz` van a la API.
- `backup`: un `pg_dump` al arrancar y otro cada 24 h.

`GET /healthz` responde `{"status":"ok"}`. `GET /readyz` responde lo mismo si la base acepta `SELECT 1`; si no, 503.

## 7. Si prod no arranca

Con `APP_MODE=prod`, api y worker levantan `ProdConfigError` y el proceso no sigue. El texto es `APP_MODE=prod no arranca: …`, con estos huecos separados por `; `:

- `falta SECRET_KEY`
- `SECRET_KEY debe tener al menos 32 caracteres`
- `falta DATABASE_URL`
- `falta ADMIN_EMAIL`
- `falta ADMIN_PASSWORD_HASH`
- `falta PUBLIC_BASE_URL`
- `PUBLIC_BASE_URL debe empezar por https`
- `falta AGENCY_NAME`
- `falta AGENCY_EMAIL`

`SECRET_KEY` vacío y `SECRET_KEY` corto no salen juntos. `PUBLIC_BASE_URL` ausente y `PUBLIC_BASE_URL` sin `https` tampoco. Dentro de Compose, `DATABASE_URL` ya va inyectada; el hueco aparece si el proceso corre en prod sin esa variable.

Las credenciales de Places, SMTP, Resend, Mercado Pago, Meta y el resto no están en esa lista. Sin ellas el proceso arranca y el canal queda deshabilitado.

## 8. Crear el admin

No es interactivo. Hay un solo usuario. La clave en claro es `ADMIN_PASSWORD` y solo la lee este comando. No se imprime. El login posterior compara contra `users.password_hash`, no contra `ADMIN_PASSWORD` ni contra `ADMIN_PASSWORD_HASH`.

`ADMIN_EMAIL` ya está en el `.env`. `ADMIN_PASSWORD` no tiene que quedar en el archivo. El `exec` no hereda la shell: hay que pasarla con `-e` (Compose la toma del entorno de esa shell).

```bash
read -r -s ADMIN_PASSWORD
export ADMIN_PASSWORD
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T -e ADMIN_PASSWORD api python main.py --mode create-admin
unset ADMIN_PASSWORD
```

Si `ADMIN_PASSWORD` ya está en el entorno del contenedor, el comando sin `-e` es:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T api python main.py --mode create-admin
```

Sale por stdout `admin creado: <correo>` o `admin actualizado: <correo>`. Si ya había una fila en `users`, actualiza esa fila (aunque cambie el correo) y no crea una segunda. Si falta la clave, stderr dice `Falta ADMIN_PASSWORD. Definila en el entorno; no la escribas en un archivo de ejemplo.` y el exit code es 2. Si falta el correo: `Falta ADMIN_EMAIL.` y también 2.

El panel queda en `https://<SITE_DOMAIN>/admin/`. `POST /api/auth/login` pone la cookie `session` (HttpOnly). Las escrituras llevan `X-CSRF-Token`.

## 9. Backups

El servicio `backup` ejecuta `backup-loop.sh`: un dump al arrancar y después cada 24 h (`sleep 86400`). Si el dump falla, reintenta a la hora. El archivo es `/backups/agencia-<fecha UTC>.dump` (formato custom). Se borran los de más de 14 días y, además, no se dejan más de 14 archivos.

`restore.sh` no toca la base de trabajo. Crea `restore_<timestamp>`, carga el dump ahí, lee `alembic_version` y la borra al salir. Sale 0 solo si esa tabla responde. Imprime `restauracion ok: restore_…`.

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T backup ls -1t /backups
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env exec -T backup /usr/local/bin/restore.sh /backups/agencia-YYYYMMDDTHHMMSSZ.dump
```

No hay en este repo un comando que vuelva atrás una migración de Alembic. No inventar un `downgrade`.

## 10. Actualizar y volver atrás

Actualizar, en la raíz del clon:

```bash
git pull
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

`migrate` vuelve a correr `alembic upgrade head`.

Volver al commit anterior es el mismo arranque, no un rollback de Alembic:

```bash
git checkout <commit-anterior>
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env up -d --build
```

Eso reconstruye las imágenes. No revierte el esquema si el upgrade nuevo ya se aplicó: no hay script de downgrade en el repo. Los volúmenes (`pgdata`, `artifacts`, `client_sites`, `caddy_data`, `backups`) se conservan.

## 11. Dueño en Windows

No hace falta Docker en el PC. Hace falta el cliente OpenSSH (en Windows 10 y 11 ya viene; si no, característica opcional «Cliente OpenSSH»).

Generar `ADMIN_PASSWORD_HASH` en el PC, desde `engine/` con el venv, con el `python -c` de arriba. Completar el `.env` en el PC. No incluir `ADMIN_PASSWORD`. No commitear el archivo.

```powershell
ssh usuario@host
scp .env usuario@host:~/Agente-IA-Autonomo/.env
```

La ruta de destino es la del clon en el VPS. Después, en la sesión SSH, `chmod 600 .env`, el `docker compose … up -d --build` de la sección 6, y el `create-admin` de la sección 8. La clave en claro se escribe en esa sesión del servidor, no viaja dentro del `.env`.
