#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $EUID -ne 0 || $# -ne 2 ]]; then echo 'Usage: sudo scripts/install_mobile_tunnel.sh TUNNEL_UUID CREDENTIAL_JSON' >&2; exit 1; fi
tunnel_id=$1
credential_path=$2
[[ $tunnel_id =~ ^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$ && -f $credential_path ]]
systemctl is-active --quiet health03-web.service
pid=$(systemctl show --property=MainPID --value health03-web.service)
upload_host=$(python3 - "$pid" <<'PY'
import http.client, pathlib, re, sys
env = dict(pair.split(b"=", 1) for pair in pathlib.Path(f"/proc/{int(sys.argv[1])}/environ").read_bytes().split(b"\0") if pair)
host = env.get(b"HEALTH03_UPLOAD_HOST", b"").decode("ascii")
if env.get(b"HEALTH03_ENV") != b"production" or env.get(b"HEALTH03_PI_APPLIANCE") != b"1":
    sys.exit("Start the production Pi web service before installing ingress")
if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
    sys.exit("Missing or invalid upload hostname")
# Verify the actual listener before installing or restarting external ingress.
headers = {
    "Host": host, "X-Forwarded-Proto": "https", "CF-Connecting-IP": "192.0.2.1",
    "X-Health03-Origin": pathlib.Path("/etc/health03/credentials/tunnel-origin-secret").read_text().strip(),
}
for path, expected in [("/api/v1/ingestion/config", 401), ("/internal/local-session", 404)]:
    conn = http.client.HTTPConnection("127.0.0.1", 8010, timeout=5)
    conn.request("GET", path, headers=headers)
    response = conn.getresponse()
    if response.status != expected:
        sys.exit(f"Phone ingress preflight failed on {path}: HTTP {response.status}")
    conn.close()
print(host)
PY
)
getent group health03-tunnel >/dev/null || groupadd --system health03-tunnel
id health03-tunnel >/dev/null 2>&1 || useradd --system --no-create-home --gid health03-tunnel --shell /usr/sbin/nologin health03-tunnel
install -d -m 0755 /etc/health03
install -d -m 0700 /etc/health03/credentials
staging=$(mktemp -d /etc/health03/tunnel-install.XXXXXXXX)
trap 'rm -rf "$staging"' EXIT
install -m 0600 "$credential_path" "$staging/tunnel.json"
sed -e "s/REPLACE_WITH_TUNNEL_UUID/$tunnel_id/g" -e "s/REPLACE_WITH_UPLOAD_HOST/$upload_host/g" "$repo_root/infra/cloudflare/mobile-upload.yml.example" > "$staging/tunnel.yml"
cloudflared --config "$staging/tunnel.yml" tunnel ingress validate
chmod 0644 "$staging/tunnel.yml"
mv "$staging/tunnel.json" /etc/health03/credentials/tunnel.json
mv "$staging/tunnel.yml" /etc/health03/tunnel.yml
install -m 0644 "$repo_root/infra/systemd/health03-tunnel.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable health03-tunnel.service
systemctl restart health03-tunnel.service
