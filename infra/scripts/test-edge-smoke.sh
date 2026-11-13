#!/usr/bin/env bash
# Smoke del borde con SITE_ADDRESS en HTTP. No publica la imagen.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

python3 - <<'PY' &
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _fmt, *_args):
        return

ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
PY
api_pid=$!
cleanup() {
  kill "$api_pid" 2>/dev/null || true
  docker rm -f agencia-edge-ci >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f agencia-edge-ci >/dev/null 2>&1 || true
docker run -d --name agencia-edge-ci --network host \
  -e ACME_EMAIL=ci@example.com \
  -e SITE_ADDRESS=http://127.0.0.1:8088 \
  -e SITE_DOMAIN=localhost \
  -e PUBLIC_ORIGIN=http://127.0.0.1:8088 \
  -e API_UPSTREAM=127.0.0.1:8765 \
  agencia-edge:ci

ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -fsS --max-time 2 http://127.0.0.1:8088/healthz | grep -q '"ok"' \
    && curl -fsS --max-time 2 http://127.0.0.1:8088/readyz | grep -q '"ok"' \
    && curl -fsS --max-time 2 -o /dev/null http://127.0.0.1:8088/ \
    && curl -fsS --max-time 2 -o /dev/null http://127.0.0.1:8088/admin/; then
    ok=1
    break
  fi
  sleep 1
done
test "$ok" = "1"
if curl -fsS --max-time 2 http://127.0.0.1:8088/api/internal/domain-check; then
  echo "domain-check no debe publicarse" >&2
  exit 1
fi
echo "edge smoke ok"
