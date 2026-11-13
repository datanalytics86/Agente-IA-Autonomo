#!/usr/bin/env bash
# El guard rechaza DRY_RUN=false y OUTREACH_ENABLED=true si ALLOW_LIVE no es true.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
guard="$root/infra/scripts/deploy-guard.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

printf 'DRY_RUN=false\nOUTREACH_ENABLED=false\n' > "$tmp/live.env"
if ALLOW_LIVE=false bash "$guard" "$tmp/live.env"; then
  echo "debio rechazar DRY_RUN=false" >&2
  exit 1
fi

printf 'DRY_RUN=true\nOUTREACH_ENABLED=true\n' > "$tmp/outreach.env"
if ALLOW_LIVE=false bash "$guard" "$tmp/outreach.env"; then
  echo "debio rechazar OUTREACH_ENABLED=true" >&2
  exit 1
fi

printf 'DRY_RUN=true\nOUTREACH_ENABLED=false\n' > "$tmp/shadow.env"
ALLOW_LIVE=false bash "$guard" "$tmp/shadow.env"
ALLOW_LIVE=true bash "$guard" "$tmp/live.env"

python3 - "$root" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
texts = [
    (root / ".github/workflows/deploy.yml").read_text(encoding="utf-8"),
    (root / ".github/workflows/deploy-target.yml").read_text(encoding="utf-8"),
]
remote = (root / "infra/scripts/deploy-remote.sh").read_text(encoding="utf-8")
for name, text in (("deploy.yml", texts[0]), ("deploy-target.yml", texts[1])):
    if "vars.DEPLOY_ENABLED == 'true'" not in text:
        raise SystemExit(f"{name} no exige DEPLOY_ENABLED")
    if "set -x" in text:
        raise SystemExit(f"{name} tiene set -x")
if "secrets.GITHUB_TOKEN" in texts[0] or "secrets.GITHUB_TOKEN" in texts[1]:
    raise SystemExit("el token no debe viajar al host")
if "SSH_PRIVATE_KEY" in remote or "GITHUB_TOKEN" in remote:
    raise SystemExit("deploy-remote.sh no debe nombrar secretos")
print("deploy guard ok")
PY
