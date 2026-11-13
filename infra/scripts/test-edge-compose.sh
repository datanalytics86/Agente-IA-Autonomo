#!/usr/bin/env bash
# base + prod: caddy no depende de web y no monta el Caddyfile ni el dist del sitio.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
envfile="$(mktemp)"
trap 'rm -f "$envfile"' EXIT
: >"$envfile"

IMAGE_TAG=abc POSTGRES_PASSWORD=abcdef0123456789 \
  ACME_EMAIL=ci@example.com \
  SITE_ADDRESS=http://127.0.0.1:8088 \
  SITE_DOMAIN=example.test \
  PUBLIC_ORIGIN=http://127.0.0.1:8088 \
  AGENCIA_ENV_FILE="$envfile" \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config \
  >/tmp/edge-compose.yml

python3 - <<'PY'
import yaml

doc = yaml.safe_load(open("/tmp/edge-compose.yml", encoding="utf-8"))
caddy = doc["services"]["caddy"]
depends = caddy.get("depends_on")
if depends is None:
    names = []
elif isinstance(depends, list):
    names = depends
elif isinstance(depends, dict):
    names = list(depends)
else:
    names = []
if "web" in names:
    raise SystemExit(f"caddy depende de web: {depends!r}")
if "api" not in names:
    raise SystemExit(f"caddy no depende de api: {depends!r}")
for mount in caddy.get("volumes") or []:
    text = mount if isinstance(mount, str) else str(mount)
    if "/etc/caddy/Caddyfile" in text or "/srv/site" in text:
        raise SystemExit(f"caddy sigue montando el demo: {text}")
print("edge compose ok")
PY
