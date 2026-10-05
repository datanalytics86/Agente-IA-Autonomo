#!/usr/bin/env bash
# Un dump al arrancar y después cada 24 h. Si falla, reintenta en 1 h.
set -euo pipefail

dest="${BACKUP_DIR:-/backups}"
mkdir -p "$dest"

while true; do
  if /usr/local/bin/backup.sh "$dest"; then
    sleep 86400
  else
    echo "backup fallo; reintento en 1 h" >&2
    sleep 3600
  fi
done
