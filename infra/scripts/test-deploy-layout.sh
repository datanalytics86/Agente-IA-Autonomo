#!/usr/bin/env bash
# docker compose config con los archivos y el cwd que usa deploy-remote.sh.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
remote="$root/infra/scripts/deploy-remote.sh"
grep -q 'releases/${image_tag}/infra/docker-compose.yml' "$remote"
grep -q 'releases/${image_tag}/infra/docker-compose.prod.yml' "$remote"

tag="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
base="$(mktemp -d)"
trap 'rm -rf "$base"' EXIT
rel="$base/releases/${tag}/infra"
mkdir -p "$rel/scripts"
cp "$root/infra/docker-compose.yml" "$root/infra/docker-compose.prod.yml" \
  "$root/infra/compose.defaults.env" "$rel/"
cp "$root/infra/scripts/backup.sh" "$rel/scripts/"
printf 'DRY_RUN=true\nOUTREACH_ENABLED=false\n' > "$base/.env"

cd "$base"
POSTGRES_PASSWORD=abcdef0123456789 docker compose -p agencia --env-file .env \
  -f "releases/${tag}/infra/docker-compose.yml" \
  -f "releases/${tag}/infra/docker-compose.prod.yml" config >/dev/null
echo "deploy layout ok"
