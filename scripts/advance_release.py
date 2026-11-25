"""Operator-only release state transitions; never infer pilot evidence."""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def advance(evidence, action, proof, now):
    if not evidence.get("technical_gates_passed"):
        raise ValueError("Technical gates must pass before pilot")
    required = json.loads(Path("docs/security/release-evidence/required-gates.json").read_text())[
        "required"
    ]
    if any(
        evidence.get("checks", {}).get(name, {}).get("status") != "passed"
        or not evidence["checks"][name].get("evidence")
        for name in required
    ):
        raise ValueError("Missing required gate evidence")
    pilot = evidence.setdefault("pilot", {})
    if action == "start-owner":
        if pilot.get("started_at"):
            raise ValueError("Pilot already started")
        pilot.update(
            started_at=now.isoformat(), owner_approval=proof, candidate_commit=evidence["commit"]
        )
        evidence["owner_pilot_allowed"] = True
    elif action == "record-doctor":
        if not pilot.get("started_at"):
            raise ValueError("Owner pilot has not started")
        pilot.update(doctor_explicitly_approved=True, doctor_evidence=proof)
    elif action == "release":
        started = dt.datetime.fromisoformat(pilot["started_at"])
        if now - started < dt.timedelta(days=7):
            raise ValueError("Seven-day owner pilot is not complete")
        if (
            not pilot.get("doctor_explicitly_approved")
            or pilot.get("candidate_commit") != evidence["commit"]
        ):
            raise ValueError("Missing doctor pilot or changed candidate")
        pilot.update(completed=True, outcome_evidence=proof, completed_at=now.isoformat())
        evidence["production_allowed"] = True
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start-owner", "record-doctor", "release"])
    parser.add_argument("--gate", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    path, proof = Path(args.gate), Path(args.evidence)
    if not proof.is_file() or not proof.stat().st_size:
        raise ValueError("A written operator approval/outcome record is required")
    record = {
        "path": str(proof.resolve()),
        "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
    }
    result = advance(json.loads(path.read_text()), args.action, record, dt.datetime.now(dt.UTC))
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


if __name__ == "__main__":
    main()
