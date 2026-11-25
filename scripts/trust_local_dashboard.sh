#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
certificate="$repo_root/.local/frontend-tls/ca.crt"
command -v certutil >/dev/null
# Snap Chromium uses its own NSS database, separate from system/OpenSSL trust.
shopt -s nullglob
for database in \
  "$HOME/.pki/nssdb/cert9.db" \
  "$HOME/.local/share/pki/nssdb/cert9.db" \
  "$HOME/snap/chromium/current/.local/share/pki/nssdb/cert9.db" \
  "$HOME"/snap/firefox/common/.mozilla/firefox/*/cert9.db \
  "$HOME"/.mozilla/firefox/*/cert9.db; do
  [[ -f "$database" ]] || continue
  certutil -A -d "sql:$(dirname -- "$database")" -n 'Health03 local development CA' -t 'C,,' -i "$certificate"
done
