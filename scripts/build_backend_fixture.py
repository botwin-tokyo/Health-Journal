import json
import uuid
from datetime import date, timedelta
from pathlib import Path

end = date(2026, 11, 7)
last = ["156.5", "156.7", "156.8", "156.6", "156.7", "156.7", "156.2"]
weights = [
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "health03-fictional-weight-" + str(i))),
        "clinical_date": (end - timedelta(days=27 - i)).isoformat(),
        "time_precision": "day",
        "value": "157.0" if i < 21 else last[i - 21],
        "unit": "lb",
    }
    for i in range(28)
]
fixture = {
    "synthetic_only": True,
    "fixture_version": "backend-1",
    "weights": weights,
    "expected": {"seven_day_mean_lb": "156.6", "fixed_reference_lb": "157.0"},
    "requested_hr_samples": [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "health03-fictional-hr-" + str(i))),
            "value": "68",
            "unit": "beats/min",
        }
        for i in range(27)
    ],
    "pulmonary": {"fev1": "3.82", "fvc": "4.87", "unit": "L"},
    "sleep": {
        "start": "2026-11-06T21:00:00-05:00",
        "end": "2026-11-07T04:30:00-05:00",
        "asleep_minutes": 408,
        "awake_minutes": 24,
        "unknown_minutes": 18,
    },
    "phone_steps": 7420,
    "workout_minutes": 34,
    "received_at": "2026-11-08T00:12:00-05:00",
}
Path("tests/fixtures/synthetic/backend-v1.json").write_text(json.dumps(fixture, indent=2) + "\n")
