#!/usr/bin/env bash
# Install the service layer for a provisioned Pi and a staged, reviewed release.
set -euo pipefail
root=/opt/health03/current
if [[ $EUID != 0 ]]; then echo 'Run as root on the provisioned Pi.' >&2; exit 1; fi
for file in /etc/health03/runtime.env "$root/.venv/bin/gunicorn" "$root/frontend/dist/index.html" /usr/bin/node; do
  [[ -f $file ]] || { echo "Missing $file" >&2; exit 1; }
done
for credential in django-secret desktop-proxy-secret smtp-password tunnel-origin-secret localhost.key localhost.pem; do
  [[ -s /etc/health03/credentials/$credential ]] || { echo "Missing $credential" >&2; exit 1; }
done
for unit in health03-local-app health03-local-worker; do
  if systemctl is-active --quiet "$unit"; then echo "Complete the planned cutover from $unit first." >&2; exit 1; fi
done
getent group health03-kms >/dev/null
getent group health03-parser-ipc >/dev/null || groupadd --system health03-parser-ipc
id health03-parser >/dev/null 2>&1 || useradd --system --gid health03-parser-ipc --no-create-home --shell /usr/sbin/nologin health03-parser
getent group health03-data >/dev/null || groupadd --system health03-data
for role in app worker retention; do
  id "health03-$role" >/dev/null 2>&1 || useradd --system --user-group --no-create-home --shell /usr/sbin/nologin "health03-$role"
done
# Read runtime.env with systemd semantics and confirm the approved release and schema
# under the actual app database role before changing any running services.
check=(systemd-run --quiet --wait --pipe --collect -p User=health03-app
  -p EnvironmentFile=/etc/health03/runtime.env)
for name in django-secret desktop-proxy-secret smtp-password tunnel-origin-secret; do
  check+=(-p "LoadCredential=$name:/etc/health03/credentials/$name")
done
"${check[@]}" /bin/sh -ec 'test "$HEALTH03_PI_APPLIANCE" = 1 || { echo "Set HEALTH03_PI_APPLIANCE=1 in runtime.env" >&2; exit 1; }'
"${check[@]}" /usr/bin/env HEALTH03_ENV=production PGUSER=health03-app "$root/.venv/bin/python" "$root/backend/manage.py" migrate --check
install -d -o root -g health03-data -m 0750 /var/lib/health03
install -d -o root -g health03-data -m 2770 /var/lib/health03/blobs
# Normalize only existing encrypted files in the production store.
find /var/lib/health03/blobs -maxdepth 1 -type f -name '*.enc' -exec chgrp health03-data {} + -exec chmod 0640 {} +
install -d -m 0755 /etc/systemd/system/health03-web.service.d
cat > /etc/systemd/system/health03-web.service.d/appliance.conf <<'UNIT'
[Service]
LoadCredential=desktop-proxy-secret:/etc/health03/credentials/desktop-proxy-secret
UNIT
# An existing unattended Pi retains its operator-provisioned shares and CA.
if [[ -d /etc/health03/unattended ]]; then
  for name in share-1 share-2 server-ca.crt; do
    [[ -s /etc/health03/unattended/$name ]] || { echo "Incomplete unattended unlock credentials" >&2; exit 1; }
  done
  install -D -m 0755 "$root/scripts/unseal_local_openbao.py" /usr/local/lib/health03/unseal_local_openbao.py
  install -m 0644 "$root/infra/systemd/health03-unseal.service" /etc/systemd/system/
  install -D -m 0644 "$root/infra/systemd/health03-openbao.service.d/unattended.conf" /etc/systemd/system/health03-openbao.service.d/unattended.conf
fi
for unit in web.service worker.service parser.service retention.service retention.timer desktop-proxy.service dashboard.service; do
  install -m 0644 "$root/infra/systemd/health03-$unit" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable health03-{web,worker,parser,desktop-proxy,dashboard}.service health03-retention.timer
systemctl restart health03-{parser,web,worker,desktop-proxy,dashboard}.service health03-retention.timer
