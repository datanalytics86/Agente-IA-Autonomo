#!/usr/bin/env bash
# Falla si el .env enciende outreach o apaga dry-run sin ALLOW_LIVE=true.
# Uso: ALLOW_LIVE=false deploy-guard.sh /ruta/.env
set -euo pipefail

file="${1:?falta el .env}"
allow="${ALLOW_LIVE:-false}"

if [ ! -f "$file" ]; then
  echo "no existe el .env: $file" >&2
  exit 1
fi

if [ "$allow" = "true" ]; then
  exit 0
fi

if grep -Eiq '^DRY_RUN=(false|0)$' "$file"; then
  echo "DRY_RUN=false sin ALLOW_LIVE" >&2
  exit 1
fi

if grep -Eiq '^OUTREACH_ENABLED=(true|1)$' "$file"; then
  echo "OUTREACH_ENABLED=true sin ALLOW_LIVE" >&2
  exit 1
fi
