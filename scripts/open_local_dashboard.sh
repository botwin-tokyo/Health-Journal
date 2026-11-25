#!/usr/bin/env bash
set -euo pipefail
for attempt in $(seq 1 120); do
  if curl --silent --fail --max-time 2 https://localhost:5173/ >/dev/null &&
     [[ $(curl --silent --max-time 2 -o /dev/null -w "%{http_code}" https://localhost:8443/api/v1/session) =~ ^(200|401)$ ]]; then
    exec /snap/bin/chromium --password-store=basic --no-first-run --new-window https://localhost:5173/overview
  fi
  sleep 2
done
exit 1
