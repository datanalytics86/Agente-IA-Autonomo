#!/usr/bin/env bash
# El guard rechaza DRY_RUN=false y OUTREACH_ENABLED=true si ALLOW_LIVE no es true.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
guard="$root/infra/scripts/deploy-guard.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

reject() {
  local name="$1"
  if ALLOW_LIVE=false bash "$guard" "$tmp/${name}.env"; then
    echo "debio rechazar ${name}" >&2
    exit 1
  fi
}

printf 'DRY_RUN=false\nOUTREACH_ENABLED=false\n' > "$tmp/live.env"
reject live
printf 'DRY_RUN="false"\nOUTREACH_ENABLED=false\n' > "$tmp/quoted.env"
reject quoted
printf 'DRY_RUN=False \nOUTREACH_ENABLED=false\n' > "$tmp/spaced.env"
reject spaced
printf 'export DRY_RUN=false\nOUTREACH_ENABLED=false\n' > "$tmp/exported.env"
reject exported
printf 'DRY_RUN=no\nOUTREACH_ENABLED=false\n' > "$tmp/no.env"
reject no
printf 'DRY_RUN=true\nOUTREACH_ENABLED=true\n' > "$tmp/outreach.env"
reject outreach
printf 'DRY_RUN=true\nexport OUTREACH_ENABLED="true"\n' > "$tmp/outreach-quoted.env"
reject outreach-quoted
printf 'DRY_RUN=true\nOUTREACH_ENABLED=yes\n' > "$tmp/outreach-yes.env"
reject outreach-yes

printf 'DRY_RUN=true\nOUTREACH_ENABLED=false\n' > "$tmp/shadow.env"
ALLOW_LIVE=false bash "$guard" "$tmp/shadow.env"
ALLOW_LIVE=true bash "$guard" "$tmp/live.env"

python3 - "$root" <<'PY'
import re
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
if "secrets.GITHUB_TOKEN" not in texts[0]:
    raise SystemExit("el build tiene que autenticarse en GHCR")
if "secrets.GITHUB_TOKEN" in texts[1] or "GITHUB_TOKEN" in remote:
    raise SystemExit("el token no debe viajar al host")
if "SSH_PRIVATE_KEY" in remote:
    raise SystemExit("deploy-remote.sh no debe nombrar secretos")
if "deploy-host-" not in texts[1]:
    raise SystemExit("el reusable tiene que usar otro grupo de concurrency")
if "/opt/agencia/logs/" not in remote:
    raise SystemExit("los logs de contenedores tienen que quedar en el host")
if "docker-compose.yml" not in remote or "docker-compose.prod.yml" not in remote:
    raise SystemExit("el deploy tiene que usar los dos compose")
if texts[1].count("scp -o BatchMode=yes") < 3:
    raise SystemExit("los scp tienen que ir con BatchMode=yes")
ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
if "caddy hash-password" not in ci:
    raise SystemExit("el hash de staging tiene que salir de caddy hash-password")
def _caddy_exacto(text: str) -> None:
    for tag in re.findall(r"caddy:(\S+)", text):
        if not re.fullmatch(r"\d+\.\d+\.\d+", tag):
            raise SystemExit(f"caddy:{tag} no es X.Y.Z")


def _postgres_xy(text: str) -> None:
    for tag in re.findall(r"postgres:(\S+)", text):
        if not re.fullmatch(r"\d+\.\d+", tag):
            raise SystemExit(f"postgres:{tag} no es X.Y")


_caddy_exacto(ci)
prod = (root / "infra/docker-compose.prod.yml").read_text(encoding="utf-8")
_postgres_xy(prod)
for malo in ("postgres:16", "postgres:latest", "postgres:16.16.1"):
    try:
        _postgres_xy(malo)
    except SystemExit:
        continue
    raise SystemExit(f"el guard dejó pasar {malo}")
for malo in ("caddy:latest", "caddy:2", "caddy:2.10"):
    try:
        _caddy_exacto(malo)
    except SystemExit:
        continue
    raise SystemExit(f"el guard dejó pasar {malo}")
if "N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy" in ci:
    raise SystemExit("el bcrypt de staging no debe ir fijo en el workflow")
print("deploy guard ok")
PY
