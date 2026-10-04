#!/usr/bin/env bash
# pg_dump (formato custom) y rotación de 14 días.
# DATABASE_URL puede ser el URI de SQLAlchemy (postgresql+psycopg://).
# La restauración está en restore.sh. El smoke lo invoca dentro del compose.

set -euo pipefail

dest="${1:-${BACKUP_DIR:-./backups}}"
mkdir -p "$dest"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${dest}/agencia-${stamp}.dump"

normalize_url() {
  printf '%s' "$1" \
    | sed -e 's|^postgresql+psycopg://|postgresql://|' \
         -e 's|^postgresql+psycopg2://|postgresql://|'
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump --format=custom --file="$out" --dbname="$(normalize_url "$DATABASE_URL")"
else
  pg_dump --format=custom --file="$out" \
    --host="${PGHOST:-localhost}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-agencia}" \
    --dbname="${PGDATABASE:-agencia}"
fi

find "$dest" -maxdepth 1 -type f -name 'agencia-*.dump' -mtime +14 -delete

shopt -s nullglob
mapfile -t sorted < <(ls -1t "${dest}"/agencia-*.dump)
if ((${#sorted[@]} > 14)); then
  for old in "${sorted[@]:14}"; do
    rm -f -- "$old"
  done
fi

echo "$out"
