#!/usr/bin/env bash
set -euo pipefail
# Run only after verifying the signed upstream checksum. No secret arguments.
if [[ $EUID -ne 0 || $# -ne 3 ]]; then
  echo 'Usage (root): install_local_openbao.sh VERIFIED_ARTIFACT_DIR SYNTHETIC_PKI_DIR REPOSITORY_DIR' >&2
  exit 1
fi
artifact_dir=$1
pki_dir=$2
repository_dir=$3
if [[ -e /etc/systemd/system/health03-openbao.service ]]; then
  echo 'Service already provisioned; review an explicit upgrade instead of overwriting it.' >&2
  exit 1
fi
getent passwd health03-bao >/dev/null || useradd --system --home-dir /var/lib/health03-openbao --shell /usr/sbin/nologin health03-bao
install -d -o root -g root -m 0755 /usr/local/lib/openbao/2.7.2
install -o root -g root -m 0755 "$artifact_dir/bao" /usr/local/lib/openbao/2.7.2/bao
if [[ ! -e /usr/local/bin/bao ]]; then
  ln -s /usr/local/lib/openbao/2.7.2/bao /usr/local/bin/bao
fi
install -d -o root -g root -m 0755 /etc/health03
install -d -o root -g health03-bao -m 0750 /etc/health03/openbao
install -o root -g health03-bao -m 0640 "$pki_dir/server.key" /etc/health03/openbao/server.key
install -o root -g health03-bao -m 0640 "$pki_dir/server.crt" /etc/health03/openbao/server.crt
install -o root -g root -m 0644 "$pki_dir/server-ca.crt" /etc/health03/bao-server-ca.crt
install -o root -g health03-bao -m 0640 "$repository_dir/infra/openbao/server.hcl" /etc/health03/openbao/server.hcl
install -o root -g root -m 0644 "$repository_dir/infra/systemd/health03-openbao.service" /etc/systemd/system/health03-openbao.service
systemctl daemon-reload
systemctl enable --now health03-openbao.service
systemctl is-active health03-openbao.service
