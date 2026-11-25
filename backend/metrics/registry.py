import json
from pathlib import Path


def definitions():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "contracts/metrics.v1.yaml").read_text()
    )["metrics"]


def capability_rows():
    return [
        {
            **row,
            "value": None,
            "availability": "awaiting_data"
            if row["capability_status"] == "implemented"
            else "awaiting_integration",
            "absent_reason": "not_recorded"
            if row["capability_status"] == "implemented"
            else "awaiting_integration",
        }
        for row in definitions()
    ]
