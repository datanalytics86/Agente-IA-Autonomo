#!/usr/bin/env bash
# El compose de producción no interpola sin IMAGE_TAG, POSTGRES_PASSWORD,
# APP_MODE ni PUBLIC_BASE_URL. La clave tiene que ser hexadecimal.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
files=(-f infra/docker-compose.yml -f infra/docker-compose.prod.yml)

must_fail() {
  if "$@" "${files[@]}" config >/tmp/compose-out.yml 2>/tmp/compose-err.txt; then
    echo "docker compose config debió fallar" >&2
    exit 1
  fi
}

must_fail env -u IMAGE_TAG -u POSTGRES_PASSWORD -u APP_MODE -u PUBLIC_BASE_URL docker compose
must_fail env -u POSTGRES_PASSWORD IMAGE_TAG=abc APP_MODE=live PUBLIC_BASE_URL=https://agencia.example docker compose
must_fail env -u IMAGE_TAG POSTGRES_PASSWORD=0000000000000000000000000000000000000000 APP_MODE=live PUBLIC_BASE_URL=https://agencia.example docker compose

envfile="$(mktemp)"
trap 'rm -f "$envfile"' EXIT
: >"$envfile"
must_fail env -u APP_MODE IMAGE_TAG=abc POSTGRES_PASSWORD=0000000000000000000000000000000000000000 \
  PUBLIC_BASE_URL=https://agencia.example AGENCIA_ENV_FILE="$envfile" docker compose
must_fail env -u PUBLIC_BASE_URL IMAGE_TAG=abc POSTGRES_PASSWORD=0000000000000000000000000000000000000000 \
  APP_MODE=live AGENCIA_ENV_FILE="$envfile" docker compose

IMAGE_TAG=abc POSTGRES_PASSWORD=0000000000000000000000000000000000000000 APP_MODE=live \
  PUBLIC_BASE_URL=https://agencia.example AGENCIA_ENV_FILE="$envfile" \
  docker compose "${files[@]}" config >/tmp/compose-out.yml

python3 - <<'PY'
import re

import yaml

doc = yaml.safe_load(open("/tmp/compose-out.yml", encoding="utf-8"))
services = doc["services"]
ports = services["db"].get("ports") or []
if ports:
    raise SystemExit(f"db publica puertos: {ports}")
url_ok = re.compile(r"postgresql://agencia:[0-9a-fA-F]+@db:5432/agencia\Z")
for name in ("api", "worker"):
    service = services[name]
    if service.get("build"):
        raise SystemExit(f"{name} todavía tiene build")
    image = service.get("image", "")
    if not image.endswith(":abc"):
        raise SystemExit(f"{name} no usa IMAGE_TAG: {image}")
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    if env.get("APP_MODE") != "live":
        raise SystemExit(f"{name} APP_MODE={env.get('APP_MODE')}")
    if env.get("PUBLIC_BASE_URL") != "https://agencia.example":
        raise SystemExit(f"{name} PUBLIC_BASE_URL={env.get('PUBLIC_BASE_URL')}")
    url = env.get("DATABASE_URL", "")
    if not url_ok.fullmatch(url):
        raise SystemExit(f"{name} DATABASE_URL no es usuario/clave-hex/host: {url}")
    if not service.get("healthcheck"):
        raise SystemExit(f"{name} no tiene healthcheck")
if not services["caddy"].get("healthcheck"):
    raise SystemExit("caddy no tiene healthcheck")
print("compose prod ok")
PY

if docker compose -f infra/docker-compose.prod.yml config >/tmp/compose-out.yml 2>/tmp/compose-err.txt; then
  echo "docker-compose.prod.yml solo no debe configurar" >&2
  exit 1
fi
if ! grep -q 'neither an image nor a build context' /tmp/compose-err.txt; then
  echo "se esperaba el error de db sin imagen" >&2
  cat /tmp/compose-err.txt >&2
  exit 1
fi

tag="0000000000000000000000000000000000000000"
base="$(mktemp -d)"
rel="$base/releases/${tag}/infra"
mkdir -p "$rel/scripts"
cp infra/docker-compose.yml infra/docker-compose.prod.yml infra/compose.defaults.env "$rel/"
cp infra/scripts/backup.sh "$rel/scripts/"
: >"$base/.env"
cd "$base"
IMAGE_TAG=abc POSTGRES_PASSWORD=0000000000000000000000000000000000000000 \
  APP_MODE=live PUBLIC_BASE_URL=https://agencia.example AGENCIA_ENV_FILE="$base/.env" \
  docker compose -p agencia --env-file .env \
  -f "releases/${tag}/infra/docker-compose.yml" \
  -f "releases/${tag}/infra/docker-compose.prod.yml" config >/dev/null
echo "compose release ok"
