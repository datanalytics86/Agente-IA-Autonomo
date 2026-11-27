#!/usr/bin/env bash
# Sin variables no hay rclone. Con el env file, sudo (env -i) cifra el dump nuevo y el tar.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
script="$root/infra/scripts/agencia-backup"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/backups" "$tmp/infra"
printf 'viejo\n' > "$tmp/backups/agencia-20200101T000000Z.dump"
touch -d '2020-01-01 00:00:00 UTC' "$tmp/backups/agencia-20200101T000000Z.dump"
: > "$tmp/infra/docker-compose.yml"
: > "$tmp/infra/docker-compose.prod.yml"
log="$tmp/calls"

cat > "$tmp/bin/docker" <<EOF
#!/bin/sh
stamp=\$(date -u +%Y%m%dT%H%M%SZ)
printf 'nuevo-dump\n' > "$tmp/backups/agencia-\${stamp}.dump"
printf 'nuevo-tar\n' > "$tmp/backups/agencia-\${stamp}-output.tar"
echo docker >> "$log"
exit 0
EOF
cat > "$tmp/bin/age" <<EOF
#!/bin/sh
out=""
prev=""
for arg in "\$@"; do
  if [ "\$prev" = "-o" ]; then out="\$arg"; fi
  prev="\$arg"
done
cp "\$prev" "\$out"
echo "age \$prev" >> "$log"
EOF
cat > "$tmp/bin/rclone" <<EOF
#!/bin/sh
echo "rclone \$*" >> "$log"
exit 0
EOF
cat > "$tmp/bin/curl" <<EOF
#!/bin/sh
echo "curl \$*" >> "$log"
exit 0
EOF
chmod +x "$tmp/bin/docker" "$tmp/bin/age" "$tmp/bin/rclone" "$tmp/bin/curl"

if PATH="$tmp/bin:/usr/bin:/bin" bash "$script"; then
  echo "debio fallar sin variables" >&2
  exit 1
fi
if [ -f "$log" ]; then
  echo "rclone corrió sin variables" >&2
  exit 1
fi

cat > "$tmp/backup.env" <<EOF
AGE_RECIPIENT=age1prueba
RCLONE_DEST=r2:agencia-backups-prod
BACKUP_DIR=$tmp/backups
HEALTHCHECKS_URL=https://hc.example/ping
EOF

mkdir -p "$tmp/bin-nodocker"
cp "$tmp/bin/age" "$tmp/bin/rclone" "$tmp/bin/curl" "$tmp/bin-nodocker/"
ln -s "$(command -v bash)" "$tmp/bin-nodocker/bash"
if env -i PATH="$tmp/bin-nodocker" \
  AGENCIA_BACKUP_ENV="$tmp/backup.env" \
  AGENCIA_COMPOSE_DIR="$tmp/infra" \
  bash "$script" >"$tmp/nodocker" 2>&1; then
  echo "sin docker el backup debe abortar" >&2
  exit 1
fi
grep -q 'falta docker' "$tmp/nodocker"

# Primer deploy: hay variables, pero todavía no existe current_tag.
if ! env -i PATH="$tmp/bin:/usr/bin:/bin" \
  AGENCIA_BACKUP_ENV="$tmp/backup.env" \
  bash "$script"; then
  echo "sin current_tag el backup no debe abortar" >&2
  exit 1
fi
if [ -f "$log" ] && grep -q rclone "$log"; then
  echo "sin current_tag no debe llamar a rclone" >&2
  exit 1
fi
rm -f "$log"

for i in $(seq 1 16); do
  printf 'old\n' > "$tmp/backups/old-${i}.age"
  touch -d "2020-01-01 00:00:$((i % 60)) UTC" "$tmp/backups/old-${i}.age"
done

env -i PATH="$tmp/bin:/usr/bin:/bin" \
  AGENCIA_BACKUP_ENV="$tmp/backup.env" \
  AGENCIA_COMPOSE_DIR="$tmp/infra" \
  AGENCIA_BACKUP_DAY=01 \
  bash "$script" --label "pre-deploy-abc"

grep -q 'nuevo-dump' "$tmp/backups"/*.dump.age
grep -q 'nuevo-tar' "$tmp/backups"/*-output.tar.age
grep -q 'rclone ' "$log"
grep -q '/daily/' "$log"
grep -q '/monthly/' "$log"
grep -q 'agencia-.*-output.tar.age' "$log"
if find "$tmp/backups" \( -name '*.dump' -o -name '*.tar' \) | grep -q .; then
  echo "quedó un dump o un tar en claro" >&2
  exit 1
fi
grep -q 'https://hc.example/ping' "$log"
if grep -q '/fail' "$log"; then
  echo "el éxito no debe pegarle a /fail" >&2
  exit 1
fi
age_count="$(find "$tmp/backups" -name '*.age' | wc -l)"
test "$age_count" -le 14
echo "agencia-backup ok"
