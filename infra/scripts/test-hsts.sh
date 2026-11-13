#!/usr/bin/env bash
# Desde el host, contra el 443 publicado por el compose de prueba:
#   curl -k -sI https://127.0.0.1/healthz
# tiene que traer Strict-Transport-Security. :80 no lo manda.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
compose=(docker compose -f infra/docker-compose.yml)

cleanup() {
  "${compose[@]}" rm -sf caddy >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
"${compose[@]}" up -d --no-deps --force-recreate caddy

published="$("${compose[@]}" port caddy 443)"
case "$published" in
  *:443) ;;
  *)
    echo "el 443 de caddy no está publicado en el host: ${published}" >&2
    exit 1
    ;;
esac

headers=""
ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if headers="$(curl -k -sI --max-time 3 https://127.0.0.1/healthz | tr -d '\r')"; then
    if printf '%s\n' "$headers" | grep -qi '^strict-transport-security: max-age=31536000; includeSubDomains$'; then
      ok=1
      break
    fi
  fi
  sleep 1
done
test "$ok" = "1"
if printf '%s\n' "$headers" | grep -qi 'preload'; then
  echo "HSTS no debe llevar preload" >&2
  exit 1
fi

http_headers="$(curl -sI --max-time 5 http://127.0.0.1/healthz | tr -d '\r')"
if printf '%s\n' "$http_headers" | grep -qi 'strict-transport-security'; then
  echo "el sitio :80 no debe enviar HSTS" >&2
  exit 1
fi
echo "hsts https ok"
