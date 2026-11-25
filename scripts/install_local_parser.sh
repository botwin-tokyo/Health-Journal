#!/usr/bin/env bash
set -euo pipefail
# Install only the sandboxed helper, not the public application or phone app.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${EUID} -ne 0 ]]; then
    echo 'Run as root to install the local parser service.' >&2
    exit 1
fi
getent group health03-parser-ipc >/dev/null || groupadd --system health03-parser-ipc
id health03-parser >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin --gid health03-parser-ipc health03-parser
id health03-worker >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin health03-worker
usermod -a -G health03-parser-ipc health03-worker
release_dir=$(mktemp -d /opt/health03-parser-release.XXXXXXXX)
chmod 0755 "$release_dir"
install -d -m 0755 "$release_dir/backend"
cp -a "$repo_root/.venv" "$release_dir/.venv"
cp -a "$repo_root/backend/parser_service" "$release_dir/backend/parser_service"
chown -R root:root "$release_dir"
chmod -R a+rX,go-w "$release_dir"
# Fixed interpreter/source paths are rewritten to this immutable local release.
sed "s|/opt/health03/current|$release_dir|g" "$repo_root/infra/systemd/health03-parser.service" > /etc/systemd/system/health03-parser.service
sed -i "s|/opt/health03/current/backend|$release_dir/backend|g" "$release_dir/backend/parser_service/server.py"
systemctl daemon-reload
systemctl reset-failed health03-parser.service || true
systemctl enable health03-parser.service
systemctl restart health03-parser.service
printf 'Installed isolated parser release: %s\n' "$release_dir"
