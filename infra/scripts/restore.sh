#!/usr/bin/env bash
# Restaura un dump custom en una base temporal y la borra.
# Uso: restore.sh /backups/agencia-YYYYMMDDTHHMMSSZ.dump
# Sale 0 solo si alembic_version responde. No toca la base de trabajo.

set -euo pipefail

dump="${1:?falta el archivo dump}"
if [[ ! -f "$dump" ]]; then
  echo "no existe: $dump" >&2
  exit 1
fi

stamp="$(date -u +%Y%m%d%H%M%S)"
tmpdb="restore_${stamp}"

cleanup() {
  psql --dbname=postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${tmpdb}" >/dev/null
}
trap cleanup EXIT

psql --dbname=postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${tmpdb}"
set +e
pg_restore --no-owner --dbname="$tmpdb" "$dump"
status=$?
set -e
if [[ "$status" -gt 1 ]]; then
  echo "pg_restore salió ${status}" >&2
  exit "$status"
fi

psql --dbname="$tmpdb" -v ON_ERROR_STOP=1 -c "SELECT version_num FROM alembic_version"
echo "restauracion ok: ${tmpdb}"
