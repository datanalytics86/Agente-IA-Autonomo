#!/usr/bin/env bash
# Caddyfile.prod rechaza los paths internos que esquivan el matcher de /api.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'if [ -f "$tmp/caddy.pid" ]; then sudo kill "$(sudo cat "$tmp/caddy.pid")" 2>/dev/null || true; fi; rm -rf "$tmp"' EXIT

mkdir -p "$tmp/site" "$tmp/admin"
printf '<html>sitio</html>\n' > "$tmp/site/index.html"
printf '<html>admin</html>\n' > "$tmp/admin/index.html"
sed \
  -e 's#reverse_proxy {$API_UPSTREAM:api:8000}#respond "proxied" 200#' \
  -e 's#admin off#admin off\n\tlocal_certs#' \
  "$root/infra/Caddyfile.prod" > "$tmp/Caddyfile"

export ACME_EMAIL=ci@example.com
export SITE_ADDRESS=http://:8099
export SITE_DOMAIN=localhost
export PUBLIC_ORIGIN=http://127.0.0.1:8099
export EDGE_AUTH=noauth
# Los hosts www/panel/api escuchan :443. En local hace falta root; en CI también.
sudo -E caddy start --config "$tmp/Caddyfile" --adapter caddyfile --pidfile "$tmp/caddy.pid" >/dev/null
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
