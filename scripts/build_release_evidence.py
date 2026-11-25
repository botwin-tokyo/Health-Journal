import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--release-id", required=True)
parser.add_argument("--results", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
required = json.loads(Path("docs/security/release-evidence/required-gates.json").read_text())[
    "required"
]
results = json.loads(Path(args.results).read_text())
checks = {
    name: results.get(name, {"status": "not_verified", "evidence": None}) for name in required
}
passed = all(row.get("status") == "passed" and row.get("evidence") for row in checks.values())
evidence = {
    "release_id": args.release_id,
    "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest(),
    "checks": checks,
    "owner_exceptions": json.loads(
        Path("docs/security/release-evidence/required-gates.json").read_text()
    ).get("owner_exceptions", {}),
    "technical_gates_passed": passed,
    "production_allowed": False,
    "pilot": {"owner_days": 0, "doctor_explicitly_approved": False, "completed": False},
}
Path(args.output).write_text(json.dumps(evidence, indent=2) + "\n")
print("Release evidence written. Production remains closed pending pilot approval/completion.")
