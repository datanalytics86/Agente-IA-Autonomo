#!/usr/bin/env bash
# Restaura un dump custom en una base que tiene que existir.
# pg_restore --clean --if-exists --no-owner, como pide el plan de backups.
# Uso: restore.sh <archivo.dump> <base_destino>
# No restaura encima de PGDATABASE salvo RESTORE_ALLOW_SOURCE=1.

set -euo pipefail

dump="${1:?falta el dump}"
target="${2:?falta la base destino}"

if [[ ! -f "$dump" ]]; then
  echo "no existe el dump: $dump" >&2
  exit 1
fi

if [[ "$target" == "${PGDATABASE:-}" && "${RESTORE_ALLOW_SOURCE:-}" != "1" ]]; then
  echo "no restauro sobre la base de origen ($target). Usa una base vacía." >&2
  exit 1
fi

pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --exit-on-error \
  --dbname="$target" \
  "$dump"
