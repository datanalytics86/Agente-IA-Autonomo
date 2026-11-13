#!/usr/bin/env bash
# Caddyfile.prod rechaza los paths internos que esquivan el matcher de /api.
# www, panel y api escucharían :443; este chequeo los quita y usa solo HTTP.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'if [ -f "$tmp/caddy.pid" ]; then kill "$(cat "$tmp/caddy.pid")" 2>/dev/null || true; fi; rm -rf "$tmp"' EXIT

sed 's#reverse_proxy {$API_UPSTREAM:api:8000}#respond "proxied" 200#' \
  "$root/infra/Caddyfile.prod" \
  | awk '
    /^www\.\{/ || /^panel\.\{/ || /^api\.\{/ { skip=1 }
    skip && /^}/ { skip=0; next }
    !skip { print }
  ' > "$tmp/Caddyfile"

export ACME_EMAIL=ci@example.com
export SITE_ADDRESS=http://:8099
export SITE_DOMAIN=localhost
export PUBLIC_ORIGIN=http://127.0.0.1:8099
export EDGE_AUTH=noauth

caddy start --config "$tmp/Caddyfile" --adapter caddyfile --pidfile "$tmp/caddy.pid" >/dev/null
sleep 0.4

reject() {
  local path="$1"
  local code
  code="$(curl -s -o "$tmp/body" -w '%{http_code}' --path-as-is "http://127.0.0.1:8099${path}")"
  if [ "$code" = "200" ] || grep -q proxied "$tmp/body"; then
    echo "el path no fue rechazado: $code $path" >&2
    exit 1
  fi
  case "$code" in
    400|404) ;;
    *) echo "se esperaba 400 o 404, llegó $code en $path" >&2; exit 1 ;;
  esac
}

reject /api/internal/domain-check
reject /API/internal/domain-check
reject '/api/internal%2Fdomain-check'
reject '/api/./internal/domain-check'

public="$(curl -s -o "$tmp/body" -w '%{http_code}' --path-as-is http://127.0.0.1:8099/api/public/paquetes)"
test "$public" = "200"
grep -q proxied "$tmp/body"
echo "caddy prod internal ok"
