#!/usr/bin/env bash
# iptables falso: el caso sano (backend iptables sobre nft), FORWARD DROP,
# reglas legacy y la mezcla real (dockerd nftables con alternativa legacy).
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
script="$root/infra/scripts/bootstrap-host.sh"
base="$(mktemp -d)"
trap 'rm -rf "$base"' EXIT

write_bin() {
  local dir="$1"
  local name="$2"
  local body="$3"
  printf '%s\n' '#!/bin/sh' "$body" > "${dir}/${name}"
  chmod +x "${dir}/${name}"
}

common() {
  local dir="$1"
  write_bin "$dir" iptables 'echo "iptables v1.8.10 (nf_tables)"'
  write_bin "$dir" iptables-legacy-save 'exit 0'
  write_bin "$dir" iptables-legacy 'echo "-P FORWARD ACCEPT"'
}

okdir="${base}/ok"
mkdir -p "$okdir"
common "$okdir"
write_bin "$okdir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$okdir" docker 'echo "Firewall Backend: iptables"'
PATH="${okdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only

dropdir="${base}/drop"
mkdir -p "$dropdir"
common "$dropdir"
write_bin "$dropdir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$dropdir" iptables-legacy 'echo "-P FORWARD DROP"'
if PATH="${dropdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "FORWARD DROP debió abortar" >&2
  exit 1
fi

legacydir="${base}/legacy"
mkdir -p "$legacydir"
common "$legacydir"
write_bin "$legacydir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$legacydir" iptables-legacy-save 'echo "-A DOCKER -j RETURN"'
if PATH="${legacydir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "una regla DOCKER en legacy debió abortar" >&2
  exit 1
fi

nodir="${base}/none"
mkdir -p "$nodir"
PATH="${nodir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=debian BOOTSTRAP_OS_VERSION=12 \
  bash "$script" --check-only

sub="${base}/sub"
mkdir -p "$sub"
common "$sub"
write_bin "$sub" update-alternatives 'echo "slave /usr/sbin/iptables-nft"; echo "Value: /usr/sbin/iptables-legacy"'
if PATH="${sub}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "un substring nft no debe tapar el enlace legacy" >&2
  exit 1
fi

bindir="${base}/binmismatch"
mkdir -p "$bindir"
common "$bindir"
write_bin "$bindir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$bindir" docker 'echo "iptables binary: /usr/sbin/iptables-legacy"'
if PATH="${bindir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "dockerd y la alternativa activa no coinciden" >&2
  exit 1
fi

mixdir="${base}/mix"
mkdir -p "$mixdir"
common "$mixdir"
write_bin "$mixdir" update-alternatives 'echo "Value: /usr/sbin/iptables-legacy"'
write_bin "$mixdir" docker 'echo "Firewall Backend: nftables"'
if PATH="${mixdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=debian BOOTSTRAP_OS_VERSION=12 \
  bash "$script" --check-only; then
  echo "dockerd nftables con alternativa legacy debió abortar" >&2
  exit 1
fi

grep -q 'apt-get install -y age rclone openssh-server sudo' "$script"
python3 - "$script" <<'PY'
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
apt = text.find("openssh-server sudo")
made = text.find("install -d -m 755 /run/sshd", apt)
if apt < 0 or made < 0 or made - apt > 250:
    raise SystemExit("/run/sshd tiene que crearse al instalar sshd, sin DEPLOY_PUBKEY")
PY
grep -q 'install -d -m 750 /etc/sudoers.d' "$script"
grep -q 'visudo -cf /etc/sudoers.d/agencia-backup' "$script"
grep -q 'rm -f /etc/sudoers.d/agencia-backup' "$script"
echo "bootstrap iptables ok"
