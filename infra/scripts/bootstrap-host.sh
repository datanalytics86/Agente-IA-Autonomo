#!/usr/bin/env bash
# Prepara un host Debian 12 o Ubuntu 24.04. Idempotente.
# --check-only no cambia nada: solo verifica el SO y iptables (§7.4).
# BOOTSTRAP_OS_ID y BOOTSTRAP_OS_VERSION existen para la prueba con comandos falsos.
# El grupo docker equivale a root: quien está ahí puede montar el disco del host.
set -euo pipefail

check_only=0
if [ "${1:-}" = "--check-only" ]; then
  check_only=1
fi

os_id="${BOOTSTRAP_OS_ID:-}"
os_version="${BOOTSTRAP_OS_VERSION:-}"
if [ -z "$os_id" ] && [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  os_id="${ID:-}"
  os_version="${VERSION_ID:-}"
fi

case "${os_id}-${os_version}" in
  debian-12|ubuntu-24.04) ;;
  *)
    echo "hace falta Debian 12 o Ubuntu 24.04 (hay ${os_id:-desconocido}-${os_version:-})" >&2
    exit 1
    ;;
esac

if [ "$check_only" -eq 0 ] && ! command -v iptables >/dev/null 2>&1; then
  apt-get update
  apt-get install -y iptables
fi

version="$(iptables --version 2>/dev/null || true)"
if ! printf '%s\n' "$version" | grep -q 'nf_tables'; then
  echo "iptables no usa nf_tables: ${version:-sin iptables}" >&2
  exit 1
fi

alt="$(update-alternatives --display iptables 2>/dev/null || true)"
if ! printf '%s\n' "$alt" | grep -q 'iptables-nft'; then
  echo "la alternativa de iptables no apunta a iptables-nft" >&2
  exit 1
fi

legacy_save="$(iptables-legacy-save 2>/dev/null || true)"
legacy_count="$(printf '%s\n' "$legacy_save" | grep -c '^-' || true)"
if [ "${legacy_count}" != "0" ]; then
  echo "hay ${legacy_count} reglas en iptables-legacy" >&2
  exit 1
fi

forward="$(iptables-legacy -S FORWARD 2>/dev/null || true)"
if printf '%s\n' "$forward" | grep -q '^-P FORWARD DROP$'; then
  echo "iptables-legacy tiene -P FORWARD DROP" >&2
  exit 1
fi

if command -v docker >/dev/null 2>&1; then
  info="$(docker info 2>/dev/null || true)"
  # Docker 28/29 dice "Firewall Backend: iptables" aunque la alternativa sea
  # iptables-nft: dockerd llama a iptables y ese binario escribe en nftables.
  # La mezcla real es nftables en dockerd con la alternativa en legacy.
  if printf '%s\n' "$info" | grep -q 'Firewall Backend: nftables'; then
    if ! printf '%s\n' "$alt" | grep -q 'iptables-nft'; then
      echo "dockerd usa nftables y la alternativa de iptables no" >&2
      exit 1
    fi
  fi
fi

echo "iptables ok (${os_id} ${os_version})"

if [ "$check_only" -eq 1 ]; then
  exit 0
fi

if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash deploy
fi
# deploy tiene que poder crear releases/ y escribir current_tag.
# El .env de /opt/agencia queda 600 y dueño deploy; este script no lo escribe.
install -d -o deploy -g deploy -m 750 /opt/agencia

if [ -n "${DEPLOY_PUBKEY:-}" ]; then
  install -d -o deploy -g deploy -m 700 /home/deploy/.ssh
  printf '%s\n' "$DEPLOY_PUBKEY" > /home/deploy/.ssh/authorized_keys
  chown deploy:deploy /home/deploy/.ssh/authorized_keys
  chmod 600 /home/deploy/.ssh/authorized_keys
fi

if [ ! -f /etc/ssh/sshd_config.d/99-agencia.conf ]; then
  printf '%s\n' 'PasswordAuthentication no' 'PermitRootLogin prohibit-password' \
    > /etc/ssh/sshd_config.d/99-agencia.conf
fi
if [ -n "${DEPLOY_PUBKEY:-}" ]; then
  sshd -t
  systemctl reload ssh || service ssh reload
fi

install -d -m 755 /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
  printf '%s\n' '{"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"5"}}' \
    > /etc/docker/daemon.json
fi

if [ ! -x /usr/bin/docker ]; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -d -m 755 /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${os_id}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
    "$(dpkg --print-architecture)" "$ID" "$VERSION_CODENAME" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
# El grupo docker equivale a root.
usermod -aG docker deploy || true

apt-get install -y unattended-upgrades
if [ "$os_id" = "debian" ] && [ ! -f /etc/apt/apt.conf.d/20auto-upgrades ]; then
  printf '%s\n' \
    'APT::Periodic::Update-Package-Lists "1";' \
    'APT::Periodic::Unattended-Upgrade "1";' \
    > /etc/apt/apt.conf.d/20auto-upgrades
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
install -m 755 "$script_dir/bootstrap-host.sh" /usr/local/sbin/bootstrap-host.sh
if [ ! -f /etc/apt/apt.conf.d/99agencia-iptables ]; then
  printf '%s\n' 'DPkg::Post-Invoke {"/usr/local/sbin/agencia-iptables-check || true";};' \
    > /etc/apt/apt.conf.d/99agencia-iptables
  install -m 755 /dev/stdin /usr/local/sbin/agencia-iptables-check <<'EOF'
#!/bin/sh
/usr/local/sbin/bootstrap-host.sh --check-only 2>&1 | logger -t agencia-iptables
EOF
fi

infra_dir="$(cd "$script_dir/.." && pwd)"
if [ -f "$infra_dir/sudoers.d/agencia-backup" ]; then
  install -o root -g root -m 440 "$infra_dir/sudoers.d/agencia-backup" /etc/sudoers.d/agencia-backup
  visudo -cf /etc/sudoers.d/agencia-backup
fi
if [ -f "$infra_dir/scripts/agencia-backup" ]; then
  install -o root -g root -m 755 "$infra_dir/scripts/agencia-backup" /usr/local/sbin/agencia-backup
fi
if [ -f "$infra_dir/systemd/agencia-backup.service" ]; then
  install -o root -g root -m 644 "$infra_dir/systemd/agencia-backup.service" /etc/systemd/system/agencia-backup.service
  install -o root -g root -m 644 "$infra_dir/systemd/agencia-backup.timer" /etc/systemd/system/agencia-backup.timer
  systemctl daemon-reload
  systemctl enable --now agencia-backup.timer
fi
