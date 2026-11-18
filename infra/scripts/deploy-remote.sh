#!/usr/bin/env bash
# Corre en el host. Argumentos: tag, backup_first, allow_live, public_url.
# No recibe secretos por la línea de comandos. El pull de GHCR es sin login.
set -euo pipefail

tag="${1:?falta el tag}"
backup_first="${2:?falta backup_first}"
allow_live="${3:?falta allow_live}"
public_url="${4:?falta public_url}"

if [[ ! "$tag" =~ ^[0-9a-f]{40}$ ]]; then
  echo "tag invalido" >&2
  exit 1
fi

cd /opt/agencia
rel="releases/${tag}/infra"
prev="$(cat current_tag 2>/dev/null || true)"
test -f .env || { echo "Falta /opt/agencia/.env"; exit 1; }

ALLOW_LIVE="$allow_live" bash /opt/agencia/deploy-guard.sh /opt/agencia/.env

dc() {
  local image_tag="$1"
  shift
  IMAGE_TAG="$image_tag" docker compose -p agencia --env-file .env \
    -f "releases/${image_tag}/infra/docker-compose.yml" \
    -f "releases/${image_tag}/infra/docker-compose.prod.yml" "$@"
}

dc "$tag" pull

if [ "$backup_first" = "true" ]; then
  sudo -n /usr/local/sbin/agencia-backup --label "pre-deploy-${tag}"
fi

dc "$tag" up -d db
dc "$tag" run --rm api alembic upgrade head
dc "$tag" up -d --remove-orphans

# Solo /healthz y /readyz. Con EDGE_AUTH=staging_auth, / y /admin/
# responden 401 y el deploy haría rollback.
smoke() {
  local _
  for _ in $(seq 1 30); do
    if curl -fsS "${public_url}/healthz" | grep -q '"ok"' \
      && curl -fsS "${public_url}/readyz" | grep -q '"ok"'; then
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
  mkdir -p /opt/agencia/logs
  dc "$tag" logs --tail=200 api worker caddy > "/opt/agencia/logs/deploy-${tag}.log" 2>&1 || true
  dc "$tag" ps || true
  curl -sS -o /dev/null -w 'healthz %{http_code}\n' "${public_url}/healthz" || true
  curl -sS -o /dev/null -w 'readyz %{http_code}\n' "${public_url}/readyz" || true
  if [ -n "$prev" ]; then
    echo "Rollback a ${prev} (solo imágenes; sin downgrade de Alembic)"
    dc "$prev" up -d --remove-orphans
    smoke && echo "Rollback OK" || echo "Rollback también falló: intervenir a mano"
  fi
  exit 1
fi
