#!/usr/bin/env bash
# Tres secretos fuera del allowlist tienen que aparecer. El historial de esta rama, no.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/tree/infra" "$tmp/tree/engine/tests" "$tmp/tree/other"

other_env="$(printf '%s%s' 'p8sW3nQ6vL1cR9mT' '4yH7bK2dF5gJ8a')"
other_pay="$(printf '%s%s' 'k7Qm9Lp2Xv8Nc4Rb6T' 'y1Uw3Zs5Hd0Fj')"
sig="$(printf '%s%s' 'x_signa' 'ture=')"

printf 'SECRET_KEY=%s\n' "$other_env" > "$tmp/tree/infra/.env.ci"
printf 'api_key = '\''%s'\''\n' "$other_pay" > "$tmp/tree/engine/tests/test_payments.py"
printf 'verify(secret="mp-secret", %s"", x_request_id="req-1")\n' "$sig" > "$tmp/tree/other/notes.py"

gitleaks detect --no-git --no-banner \
  --source "$tmp/tree" \
  --config "$root/.gitleaks.toml" \
  --report-format json \
  --report-path "$tmp/planted.json" \
  --exit-code 0 >/dev/null

python3 - "$tmp/planted.json" "$other_env" "$other_pay" <<'PY'
import json
import sys

report, other_env, other_pay = sys.argv[1:]
items = json.load(open(report, encoding="utf-8"))
if len(items) != 3:
    raise SystemExit(f"se esperaban 3 hallazgos, hay {len(items)}: {items}")
found = {(item["File"].split("/tree/")[-1], item.get("Secret") or "") for item in items}
empty_sig = "x_signa" + "ture="
expected = {
    ("infra/.env.ci", other_env),
    ("engine/tests/test_payments.py", other_pay),
    ("other/notes.py", empty_sig),
}
if found != expected:
    raise SystemExit(f"hallazgos inesperados: {found}")
print("gitleaks planted ok")
PY

gitleaks detect --no-banner \
  --log-opts="HEAD" \
  --source "$root" \
  --config "$root/.gitleaks.toml" \
  --report-format json \
  --report-path "$tmp/history.json" \
  --exit-code 0 >/dev/null

python3 - "$tmp/history.json" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1], encoding="utf-8"))
if items:
    shown = [f"{item.get('Commit','')[:10]} {item.get('File')} {item.get('Secret')}" for item in items]
    raise SystemExit("el historial de HEAD no está limpio:\n" + "\n".join(shown))
print("gitleaks history ok")
PY
