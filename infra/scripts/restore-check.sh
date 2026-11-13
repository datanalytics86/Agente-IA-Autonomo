#!/usr/bin/env bash
# Dump de la base de origen y restore en una base temporal.
# Compara conteos por tabla y su checksum. Borra la temporal al salir.
# El cliente tiene que ser de la misma generación que el servidor.
# pg_dump 17 o más nuevo manda `SET transaction_timeout` y Postgres 16 lo rechaza.
# Conexión por variables libpq: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE.
# No usa servicios de pago.

set -euo pipefail

src_db="${PGDATABASE:-agencia}"
temp_db="restore_check_$$"
dump="$(mktemp)"
src_counts="$(mktemp)"
dst_counts="$(mktemp)"

cleanup() {
  local status=$?
  psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${temp_db} WITH (FORCE)" >/dev/null 2>&1 || true
  rm -f "$dump" "$src_counts" "$dst_counts"
  exit "$status"
}
trap cleanup EXIT

if [[ "$temp_db" == "$src_db" ]]; then
  echo "la base temporal coincide con la de origen" >&2
  exit 1
fi

pg_dump --format=custom --no-owner --file="$dump" --dbname="$src_db"
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${temp_db}"
pg_restore --no-owner --no-acl --exit-on-error --dbname="$temp_db" "$dump"

write_counts() {
  local db="$1"
  local out="$2"
  local tables rel cnt
  : >"$out"
  tables="$(psql -d "$db" -v ON_ERROR_STOP=1 -At -c "
    SELECT quote_ident(n.nspname) || '.' || quote_ident(c.relname)
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'r'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY 1
  ")"
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    cnt="$(psql -d "$db" -v ON_ERROR_STOP=1 -At -c "SELECT count(*) FROM ${rel}")"
    printf '%s %s\n' "$rel" "$cnt" >>"$out"
  done <<<"$tables"
}

write_counts "$src_db" "$src_counts"
write_counts "$temp_db" "$dst_counts"

src_sum="$(sha256sum "$src_counts" | awk '{print $1}')"
dst_sum="$(sha256sum "$dst_counts" | awk '{print $1}')"
echo "source_checksum=${src_sum}"
echo "restore_checksum=${dst_sum}"
if ! cmp -s "$src_counts" "$dst_counts"; then
  echo "los conteos no coinciden" >&2
  diff -u "$src_counts" "$dst_counts" >&2 || true
  exit 1
fi
echo "ok"
