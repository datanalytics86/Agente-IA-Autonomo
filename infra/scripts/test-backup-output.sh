#!/usr/bin/env bash
# Prueba el archivo de engine_output sin Postgres ni Docker.
# pg_dump es un sustituto que solo escribe el archivo pedido.

set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin" "$tmp/output/demo" "$tmp/dest"
printf 'pagina\n' > "$tmp/output/demo/index.html"

cat > "$tmp/bin/pg_dump" <<'EOF'
#!/bin/sh
file=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "--file" ]; then
    file="$arg"
  fi
  case "$arg" in
    --file=*) file="${arg#--file=}" ;;
  esac
  prev="$arg"
done
if [ -z "$file" ]; then
  echo "fake pg_dump: falta --file" >&2
  exit 1
fi
printf 'PGDMP' > "$file"
EOF
chmod +x "$tmp/bin/pg_dump"

env -u DATABASE_URL \
  PATH="$tmp/bin:$PATH" \
  PGHOST=localhost \
  PGPORT=5432 \
  PGUSER=agencia \
  PGDATABASE=agencia \
  ENGINE_OUTPUT_DIR="$tmp/output" \
  bash "$root/infra/scripts/backup.sh" "$tmp/dest"

dump="$(find "$tmp/dest" -name 'agencia-*.dump' -print -quit)"
archive="$(find "$tmp/dest" -name 'agencia-*-output.tar' -print -quit)"
test -n "$dump"
test -n "$archive"
tar -tf "$archive" | grep -q 'demo/index.html'

compose="$root/infra/docker-compose.prod.yml"
grep -q 'name: engine_output' "$compose"
grep -q 'engine_output:/app/output' "$compose"
grep -q 'engine_output:/srv/output:ro' "$compose"
grep -q 'engine_output:/engine-output:ro' "$compose"
grep -q 'AGENCY_OUTPUT_DIR: /app/output' "$compose"
grep -q 'CLIENT_SITES_DIR: /app/output/clients' "$compose"

echo "backup output ok"
