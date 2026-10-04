#!/usr/bin/env bash
# Restauración se prueba en F7. Este script no restaura.
# No lo ejecutes contra una base real antes de esa prueba.
# pg_dump (formato custom) y rotación de 14 archivos.
# DATABASE_URL tiene que ser un URI de libpq (postgresql://...), no el de SQLAlchemy.
# Si no hay DATABASE_URL, usa PGHOST, PGPORT, PGUSER y PGDATABASE.

set -euo pipefail

dest="${1:-${BACKUP_DIR:-./backups}}"
mkdir -p "$dest"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${dest}/agencia-${stamp}.dump"

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump --format=custom --file="$out" --dbname="$DATABASE_URL"
else
  pg_dump --format=custom --file="$out" \
    --host="${PGHOST:-localhost}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-agencia}" \
    --dbname="${PGDATABASE:-agencia}"
fi

shopt -s nullglob
dumps=("${dest}"/agencia-*.dump)
if ((${#dumps[@]} > 14)); then
  mapfile -t sorted < <(ls -1t "${dest}"/agencia-*.dump)
  for old in "${sorted[@]:14}"; do
    rm -f -- "$old"
  done
fi
