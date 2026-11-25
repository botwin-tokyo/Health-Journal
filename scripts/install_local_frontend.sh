#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
"$repo_root/scripts/trust_local_dashboard.sh"
unit_dir="$HOME/.config/systemd/user"
mkdir -p "$unit_dir"
for task in dashboard api-proxy; do
  script=local_dashboard.mjs
  [[ $task == api-proxy ]] && script=local_api_proxy.mjs
  cat > "$unit_dir/health03-$task.service" <<UNIT
[Unit]
Description=Health03 local $task
After=network.target
[Service]
WorkingDirectory=$repo_root
ExecStart=$(command -v node) $repo_root/scripts/$script
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
UMask=0077
[Install]
WantedBy=default.target
UNIT
done
systemctl --user daemon-reload
systemctl --user enable --now health03-api-proxy.service health03-dashboard.service
