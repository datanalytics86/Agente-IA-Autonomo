#!/usr/bin/env bash
# Corre en el host. Argumentos: tag, backup_first, allow_live, public_url.
# No recibe secretos por la línea de comandos. El pull de GHCR es sin login.
set -euo pipefail

tag="${1:?falta el tag}"
backup_first="${2:?falta backup_first}"
allow_live="${3:?falta allow_live}"
public_url="${4:?falta public_url}"

cd /opt/agencia
rel="releases/${tag}"
prev="$(cat current_tag 2>/dev/null || true)"
test -f .env || { echo "Falta /opt/agencia/.env"; exit 1; }

ALLOW_LIVE="$allow_live" /opt/agencia/deploy-guard.sh /opt/agencia/.env

dc() {
  local image_tag="$1"
  shift
  IMAGE_TAG="$image_tag" docker compose -p agencia --env-file .env \
    -f "releases/${image_tag}/docker-compose.prod.yml" "$@"
}

dc "$tag" pull

if [ "$backup_first" = "true" ]; then
  sudo -n /usr/local/sbin/agencia-backup --label "pre-deploy-${tag}"
fi

dc "$tag" up -d db
dc "$tag" run --rm api alembic upgrade head
dc "$tag" up -d --remove-orphans

smoke() {
  local i
  for i in $(seq 1 30); do
    if curl -fsS "${public_url}/healthz" | grep -q '"ok"' \
      && curl -fsS "${public_url}/readyz" | grep -q '"ok"' \
      && curl -fsS -o /dev/null "${public_url}/" \
      && curl -fsS -o /dev/null "${public_url}/admin/"; then
      return 0
    fi
    sleep 5
  done
  return 1
}

if smoke; then
  printf '%s\n' "$tag" > current_tag
  echo "OK ${tag}"
else
  echo "Smoke test falló en ${tag}"
  dc "$tag" logs --tail=200 api worker caddy || true
  if [ -n "$prev" ]; then
    echo "Rollback a ${prev} (solo imágenes; sin downgrade de Alembic)"
    dc "$prev" up -d --remove-orphans
    smoke && echo "Rollback OK" || echo "Rollback también falló: intervenir a mano"
  fi
  exit 1
fi
