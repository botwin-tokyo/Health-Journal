"""Report paths/rule names only; never echo a matched secret."""

import re
import subprocess
from pathlib import Path

patterns = {
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(rb"(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}"),
    "bao_token": re.compile(rb"hv[sb]\.[A-Za-z0-9_-]{24,}"),
}
failures = []
for raw in subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0"):
    if not raw:
        continue
    path = Path(raw.decode())
    if not path.is_file():
        continue
    content = path.read_bytes()
    for name, pattern in patterns.items():
        if pattern.search(content):
            failures.append({"path": str(path), "rule": name})
    if path.name == ".env" or ".secrets" in path.parts or ".local" in path.parts:
        failures.append({"path": str(path), "rule": "private_runtime_path"})
for finding in failures:
    print(finding["path"] + ": " + finding["rule"])
raise SystemExit(1 if failures else 0)
