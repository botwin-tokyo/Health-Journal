#!/usr/bin/env bash
set -u
# Run once after the implementation pass. Every command's exit code is retained.
release_id=${1:?release identifier required}
case "$release_id" in *[!a-zA-Z0-9_-]*|'') exit 2 ;; esac
output_dir=".local/security-evidence/$release_id"
mkdir -p "$output_dir"
chmod 0700 "$output_dir"
run_gate() {
  gate=$1
  shift
  "$@" >"$output_dir/$gate.log" 2>&1
  result=$?
  printf '%s\t%s\n' "$gate" "$result" >> "$output_dir/results.tsv"
}
: > "$output_dir/results.tsv"
run_gate django uv run python backend/manage.py check
run_gate migrations uv run python backend/manage.py makemigrations --check --dry-run
run_gate contracts python3 scripts/check_security_contracts.py
run_gate lint uv run ruff check --config pyproject.toml backend tests scripts
run_gate secrets python3 scripts/scan_tracked_secrets.py
run_gate tests uv run pytest -q --junitxml="$output_dir/tests.xml"
run_gate dependencies uv run pip-audit --format cyclonedx-json --output "$output_dir/sbom.json"
run_gate static uv run bandit -r backend -ll -f json -o "$output_dir/static.json"
printf 'Evidence directory: %s\n' "$output_dir"
cat "$output_dir/results.tsv"
