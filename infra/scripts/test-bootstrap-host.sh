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

echo "bootstrap iptables ok"
