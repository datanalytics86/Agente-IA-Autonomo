#!/usr/bin/env bash
# Los paths que esquivan el matcher obvio no deben llegar al proxy de /api.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'if [ -f "$tmp/caddy.pid" ]; then kill "$(cat "$tmp/caddy.pid")" 2>/dev/null || true; fi; rm -rf "$tmp"' EXIT

mkdir -p "$tmp/site"
printf '<html>sitio</html>\n' > "$tmp/site/index.html"
# El sitio https:// del compose de prueba escucha :443. Este chequeo solo
# mira el HTTP, en un puerto alto, para no pedir root.
sed \
  -e 's#^:80 {#:8088 {#' \
  -e 's#^http://:80 {#http://:8088 {#' \
  -e 's#reverse_proxy api:8000#respond "proxied" 200#' \
  -e 's#reverse_proxy web:80#respond "web" 200#' \
  -e "s#root \\* /srv/site#root * $tmp/site#" \
  "$root/infra/Caddyfile" \
  | awk '/^https:\/\// { skip=1 } skip && /^}/ { skip=0; next } !skip { print }' \
  > "$tmp/Caddyfile"

caddy start --config "$tmp/Caddyfile" --adapter caddyfile --pidfile "$tmp/caddy.pid" >/dev/null
sleep 0.3

reject() {
  local path="$1"
  local code
  code="$(curl -s -o "$tmp/body" -w '%{http_code}' --path-as-is "http://127.0.0.1:8088${path}")"
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

public="$(curl -s -o "$tmp/body" -w '%{http_code}' --path-as-is http://127.0.0.1:8088/api/public/paquetes)"
test "$public" = "200"
grep -q proxied "$tmp/body"
echo "caddy internal ok"
