#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
desktop_user=${SUDO_USER:?Run with sudo from the desktop account}
desktop_home=$(getent passwd "$desktop_user" | cut -d: -f6)
desktop_group=$(id -gn "$desktop_user")
[[ -d $desktop_home && $desktop_user != root ]]
operator="$desktop_home"/.local/share/health03/operator
install -d -m 0700 /etc/health03/unattended
for number in 1 2; do
  install -o root -g root -m 0600 "$operator/synthetic-recovery/share-$number" "/etc/health03/unattended/share-$number"
done
install -o root -g root -m 0600 "$operator/synthetic-pki/server-ca.crt" /etc/health03/unattended/server-ca.crt
install -d -m 0755 /usr/local/lib/health03 /etc/systemd/system/health03-openbao.service.d
install -o root -g root -m 0755 "$repo_root/scripts/unseal_local_openbao.py" /usr/local/lib/health03/unseal_local_openbao.py
install -m 0644 "$repo_root/infra/systemd/health03-openbao.service.d/unattended.conf" /etc/systemd/system/health03-openbao.service.d/unattended.conf
install -m 0644 "$repo_root/infra/systemd/health03-unseal.service" /etc/systemd/system/health03-unseal.service
for service in health03-local-app health03-local-worker health03-bao-agent; do
  install -d -m 0755 "/etc/systemd/system/$service.service.d"
  cat > "/etc/systemd/system/$service.service.d/startup.conf" <<'EOF'
[Unit]
Wants=postgresql.service health03-openbao.service health03-unseal.service health03-parser.service
After=postgresql.service health03-openbao.service health03-unseal.service health03-parser.service
EOF
done
systemctl daemon-reload
systemctl enable health03-unseal postgresql health03-openbao health03-bao-agent health03-parser health03-local-app health03-local-worker health03-tunnel
install -m 0755 "$repo_root/scripts/open_local_dashboard.sh" /usr/local/lib/health03/open_local_dashboard.sh
loginctl enable-linger "$desktop_user"
install -d -o "$desktop_user" -g "$desktop_group" -m 0755 "$desktop_home/.config/autostart"
install -o "$desktop_user" -g "$desktop_group" -m 0644 "$repo_root/infra/desktop/health03-dashboard.desktop" "$desktop_home/.config/autostart/health03-dashboard.desktop"
