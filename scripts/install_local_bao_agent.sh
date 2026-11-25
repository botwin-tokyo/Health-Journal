#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 || $# -ne 3 ]]; then
  echo 'Usage (root): install_local_bao_agent.sh SYNTHETIC_PKI_DIR REPOSITORY_DIR LOCAL_DEVELOPER' >&2
  exit 1
fi
pki_dir=$1
repository_dir=$2
local_developer=$3
if [[ -e /etc/systemd/system/health03-bao-agent.service ]]; then
  echo 'Agent already provisioned; review an explicit upgrade instead.' >&2
  exit 1
fi
getent group health03-kms >/dev/null || groupadd --system health03-kms
getent passwd health03-agent >/dev/null || useradd --system --gid health03-kms --home-dir /nonexistent --shell /usr/sbin/nologin health03-agent
getent passwd health03-app >/dev/null || useradd --system --groups health03-kms --home-dir /nonexistent --shell /usr/sbin/nologin health03-app
# Current operator/developer receives the synthetic app boundary, not operator key-admin rights.
usermod -a -G health03-kms "$local_developer"
install -d -o root -g root -m 0700 /etc/health03/credentials
install -o root -g root -m 0600 "$pki_dir/health03-app.key" /etc/health03/credentials/bao-agent.key
install -d -o root -g health03-kms -m 0750 /etc/health03/bao-agent
install -o root -g health03-kms -m 0640 "$pki_dir/health03-app.crt" /etc/health03/bao-agent/client.crt
install -o root -g health03-kms -m 0640 "$repository_dir/infra/openbao/agent.hcl" /etc/health03/bao-agent/agent.hcl
install -o root -g root -m 0644 "$repository_dir/infra/systemd/health03-bao-agent.service" /etc/systemd/system/health03-bao-agent.service
systemctl daemon-reload
systemctl enable --now health03-bao-agent.service
