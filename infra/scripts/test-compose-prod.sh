#!/usr/bin/env bash
# El compose de producción no interpola sin IMAGE_TAG y POSTGRES_PASSWORD.
# Con ambos, db no publica puertos y api/worker no tienen build.
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

must_fail env -u IMAGE_TAG -u POSTGRES_PASSWORD docker compose
must_fail env -u POSTGRES_PASSWORD IMAGE_TAG=abc docker compose
must_fail env -u IMAGE_TAG POSTGRES_PASSWORD=solo-prueba docker compose

envfile="$(mktemp)"
trap 'rm -f "$envfile"' EXIT
: >"$envfile"
IMAGE_TAG=abc POSTGRES_PASSWORD=solo-prueba AGENCIA_ENV_FILE="$envfile" \
  docker compose "${files[@]}" config >/tmp/compose-out.yml

python3 - <<'PY'
import yaml

doc = yaml.safe_load(open("/tmp/compose-out.yml", encoding="utf-8"))
services = doc["services"]
ports = services["db"].get("ports") or []
if ports:
    raise SystemExit(f"db publica puertos: {ports}")
for name in ("api", "worker"):
    service = services[name]
    if service.get("build"):
        raise SystemExit(f"{name} todavía tiene build")
    image = service.get("image", "")
    if not image.endswith(":abc"):
        raise SystemExit(f"{name} no usa IMAGE_TAG: {image}")
print("compose prod ok")
PY
