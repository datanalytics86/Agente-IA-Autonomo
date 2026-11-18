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
IMAGE_TAG=abc POSTGRES_PASSWORD=0000000000000000000000000000000000000000 \
  APP_MODE=live PUBLIC_BASE_URL=https://agencia.example \
  AGENCIA_ENV_FILE="$base/.env" \
  ACME_EMAIL=ci@example.com SITE_ADDRESS=https://agencia.example \
  SITE_DOMAIN=agencia.example PUBLIC_ORIGIN=https://agencia.example \
  docker compose -p agencia --env-file .env \
  -f "releases/${tag}/infra/docker-compose.yml" \
  -f "releases/${tag}/infra/docker-compose.prod.yml" config >/dev/null
echo "deploy layout ok"
