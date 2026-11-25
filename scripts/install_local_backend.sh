#!/usr/bin/env bash
set -euo pipefail
# Empty-development deployment only. Production retains the explicit release gate.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${EUID} -ne 0 ]]; then echo 'Run as root.' >&2; exit 1; fi
getent group health03-data >/dev/null || groupadd --system health03-data
id health03-app >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin health03-app
id health03-worker >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin health03-worker
install -d -m 2770 -o health03-app -g health03-data /var/lib/health03-dev /var/lib/health03-dev/blobs
install -d -m 0700 /etc/health03-dev
install -m 0600 "$repo_root/.local/django-secret" /etc/health03-dev/django-secret
deployment_revision=$(git -c safe.directory="$repo_root" -C "$repo_root" rev-parse HEAD)
release_dir=$(mktemp -d /opt/health03-backend-release.XXXXXXXX)
chmod 0755 "$release_dir"
cp -a "$repo_root/backend" "$repo_root/contracts" "$repo_root/infra" "$repo_root/.venv" "$release_dir/"
chown -R root:root "$release_dir"
chmod -R a+rX,go-w "$release_dir"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d health03_dev < "$repo_root/infra/postgresql/roles.sql" >/dev/null
sudo -u postgres psql -v ON_ERROR_STOP=1 -d health03_dev < "$repo_root/infra/postgresql/audit-privileges.sql" >/dev/null
for role in app worker; do
  unit=/etc/systemd/system/health03-local-${role}.service
  if [[ $role == app ]]; then
    launch="$release_dir/.venv/bin/python -m gunicorn -c $release_dir/infra/gunicorn/config.py config.wsgi:application"
  else
    launch="$release_dir/.venv/bin/python $release_dir/backend/manage.py run_backend_worker"
  fi
  cat > "$unit" <<UNIT
[Unit]
Description=Health03 local synthetic $role (loopback only)
After=postgresql.service health03-bao-agent.service health03-parser.service
[Service]
User=health03-$role
Group=health03-data
SupplementaryGroups=health03-kms health03-parser-ipc
WorkingDirectory=$release_dir/backend
Environment=HEALTH03_DEPLOYED_REVISION=$deployment_revision HEALTH03_ENV=development HEALTH03_LOCAL_DESKTOP=1 FRONTEND_ORIGIN=https://localhost:5173 API_ORIGIN=https://localhost:8443 PGDATABASE=health03_dev PGUSER=health03-$role HEALTH03_SHARED_BLOBS=1 HEALTH03_BLOB_ROOT=/var/lib/health03-dev/blobs
LoadCredential=django-secret:/etc/health03-dev/django-secret
ExecStart=$launch
ReadWritePaths=/var/lib/health03-dev
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
CapabilityBoundingSet=
LimitCORE=0
[Install]
WantedBy=multi-user.target
UNIT
 done
systemctl daemon-reload
systemctl enable health03-local-app.service health03-local-worker.service
systemctl restart health03-local-app.service health03-local-worker.service
printf 'Local-only development backend installed: %s\n' "$release_dir"
