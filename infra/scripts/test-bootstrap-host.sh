#!/usr/bin/env bash
# Tres casos de iptables con comandos falsos: ok, FORWARD DROP y mezcla.
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

run_case() {
  local name="$1"
  local dir="${base}/${name}"
  mkdir -p "$dir"
  shift
  # remaining args are name=body pairs written by the caller via env files
  PATH="${dir}:${PATH}" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
    bash "$script" --check-only
}

okdir="${base}/ok"
mkdir -p "$okdir"
write_bin "$okdir" iptables 'echo "iptables v1.8.10 (nf_tables)"'
write_bin "$okdir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$okdir" iptables-legacy-save 'exit 0'
write_bin "$okdir" iptables-legacy 'echo "-P FORWARD ACCEPT"'
write_bin "$okdir" docker 'exit 0'
PATH="${okdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only

dropdir="${base}/drop"
mkdir -p "$dropdir"
write_bin "$dropdir" iptables 'echo "iptables v1.8.10 (nf_tables)"'
write_bin "$dropdir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$dropdir" iptables-legacy-save 'exit 0'
write_bin "$dropdir" iptables-legacy 'echo "-P FORWARD DROP"'
if PATH="${dropdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "FORWARD DROP debió abortar" >&2
  exit 1
fi

mixdir="${base}/mix"
mkdir -p "$mixdir"
write_bin "$mixdir" iptables 'echo "iptables v1.8.10 (nf_tables)"'
write_bin "$mixdir" update-alternatives 'echo "Value: /usr/sbin/iptables-nft"'
write_bin "$mixdir" iptables-legacy-save 'exit 0'
write_bin "$mixdir" iptables-legacy 'echo "-P FORWARD ACCEPT"'
write_bin "$mixdir" docker 'echo "Firewall Backend: iptables"'
if PATH="${mixdir}:/usr/bin:/bin" BOOTSTRAP_OS_ID=ubuntu BOOTSTRAP_OS_VERSION=24.04 \
  bash "$script" --check-only; then
  echo "la mezcla de backends debió abortar" >&2
  exit 1
fi

echo "bootstrap iptables ok"
