#!/usr/bin/env bash
set -euo pipefail

# Run this script locally with a sudo-capable account.
# It installs and starts OpenSSH server, then permits SSH from the private LAN.

LAN_CIDR="${LAN_CIDR:-192.168.1.0/24}"
SSH_PORT="${SSH_PORT:-22}"

sudo apt-get update
sudo apt-get install -y openssh-server
sudo systemctl enable --now ssh

if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow from "$LAN_CIDR" to any port "$SSH_PORT" proto tcp
fi

printf '\nOpenSSH is active. LAN address(es):\n'
hostname -I
printf '\nFrom another device on the same LAN, connect with:\n'
printf 'ssh %s@<LAN_IP>\n' "$(id -un)"
printf '\nVerify on this machine with:\n'
printf 'ss -tlnp | grep :%s\n' "$SSH_PORT"
