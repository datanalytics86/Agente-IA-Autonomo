#!/usr/bin/env bash
# Sin variables, rclone no se ejecuta. Con variables, los falsos registran la llamada.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
script="$root/infra/scripts/agencia-backup"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/backups"
printf 'dump\n' > "$tmp/backups/agencia-20260101T000000Z.dump"
log="$tmp/calls"

cat > "$tmp/bin/rclone" <<EOF
#!/bin/sh
echo rclone >> "$log"
exit 0
EOF
cat > "$tmp/bin/age" <<EOF
#!/bin/sh
echo age >> "$log"
out=""
prev=""
for arg in "\$@"; do
  if [ "\$prev" = "-o" ]; then out="\$arg"; fi
  prev="\$arg"
done
printf 'age\n' > "\$out"
EOF
cat > "$tmp/bin/curl" <<EOF
#!/bin/sh
echo curl >> "$log"
exit 0
EOF
chmod +x "$tmp/bin/rclone" "$tmp/bin/age" "$tmp/bin/curl"

if PATH="$tmp/bin:/usr/bin:/bin" bash "$script"; then
  echo "debio fallar sin variables" >&2
  exit 1
fi
if [ -f "$log" ]; then
  echo "rclone corrió sin variables" >&2
  exit 1
fi

PATH="$tmp/bin:/usr/bin:/bin" \
  AGE_RECIPIENT=age1prueba \
  RCLONE_DEST=r2:agencia-backups-prod \
  BACKUP_DIR="$tmp/backups" \
  HEALTHCHECKS_URL=https://hc.example/ping \
  bash "$script" --label "pre-deploy-abc"
grep -qx age "$log"
grep -qx rclone "$log"
grep -qx curl "$log"
find "$tmp/backups" -name '*.dump.age' | grep -q .
echo "agencia-backup ok"
