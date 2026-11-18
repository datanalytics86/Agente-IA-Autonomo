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
must_fail env -u IMAGE_TAG POSTGRES_PASSWORD=abcdef0123456789 APP_MODE=live PUBLIC_BASE_URL=https://agencia.example docker compose

envfile="$(mktemp)"
trap 'rm -f "$envfile"' EXIT
: >"$envfile"
must_fail env -u APP_MODE IMAGE_TAG=abc POSTGRES_PASSWORD=abcdef0123456789 \
  PUBLIC_BASE_URL=https://agencia.example AGENCIA_ENV_FILE="$envfile" docker compose
must_fail env -u PUBLIC_BASE_URL IMAGE_TAG=abc POSTGRES_PASSWORD=abcdef0123456789 \
  APP_MODE=live AGENCIA_ENV_FILE="$envfile" docker compose

IMAGE_TAG=abc POSTGRES_PASSWORD=abcdef0123456789 APP_MODE=live \
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
print("compose prod ok")
PY
