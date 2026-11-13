#!/usr/bin/env bash
# :443 con tls internal responde y manda HSTS. :80 no lo manda.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

sudo caddy stop >/dev/null 2>&1 || true
sudo caddy start --config infra/Caddyfile --adapter caddyfile >/dev/null
cleanup() { sudo caddy stop >/dev/null 2>&1 || true; }
trap cleanup EXIT

ok=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -skI --max-time 3 https://127.0.0.1/ | tr -d '\r' | grep -qi '^strict-transport-security: max-age=31536000; includeSubDomains$'; then
    ok=1
    break
  fi
  sleep 0.4
done
test "$ok" = "1"

headers="$(curl -skI --max-time 5 https://127.0.0.1/ | tr -d '\r')"
printf '%s\n' "$headers" | grep -qi '^strict-transport-security: max-age=31536000; includeSubDomains$'
if printf '%s\n' "$headers" | grep -qi 'preload'; then
  echo "HSTS no debe llevar preload" >&2
  exit 1
fi

http_headers="$(curl -sI --max-time 5 http://127.0.0.1/ | tr -d '\r')"
if printf '%s\n' "$http_headers" | grep -qi 'strict-transport-security'; then
  echo "el sitio :80 no debe enviar HSTS" >&2
  exit 1
fi
echo "hsts https ok"
