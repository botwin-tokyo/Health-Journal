#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
parser_dir=$(systemctl show --property=WorkingDirectory --value health03-parser.service)
acceptance_file=$(mktemp /tmp/health03-parser-acceptance.XXXXXXXX.py)
trap 'rm -f "$acceptance_file"' EXIT
install -m 0644 "$repo_root/scripts/parser_acceptance.py" "$acceptance_file"
sudo -u health03-worker env PYTHONPATH="$parser_dir" "${parser_dir%/backend}/.venv/bin/python" "$acceptance_file"
