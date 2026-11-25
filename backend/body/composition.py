"""Populate body cards from the actual authorized observations for the selected date."""

from ingest.contract import registry
from records import service

from .display import convert, unit

METRICS = [
    ("weight", "Weight"),
    ("bmi", "BMI"),
    ("body_fat", "Body fat"),
    ("fat_free_mass", "Fat-free mass"),
    ("fat_mass", "Fat mass"),
    ("subcutaneous_fat", "Subcutaneous fat"),
    ("visceral_fat", "Visceral fat"),
    ("water", "Body water"),
    ("skeletal_muscle", "Skeletal muscle"),
    ("muscle_mass", "Muscle mass"),
    ("bone_mass", "Bone mass"),
    ("protein", "Protein"),
    ("bmr", "BMR"),
    ("metabolic_age", "Metabolic age"),
]


def cards(request, day, representative=None):
    rows = service.permitted(request, ["weight", "body_observation"], str(day), str(day), 200)[
        "items"
    ]
    selected = unit(request)
    reference = (representative or {}).get("data", {}).get("measured_start")
    grouped = {}
    for row in rows:
        data = row["data"]
        key = registry()["aliases"].get(data.get("metric_id"), data.get("metric_id"))
        grouped.setdefault(key, []).append(row)
    result = []
    for key, label in METRICS:
        candidates = grouped.get(key, [])
        row = max(
            candidates,
            key=lambda r: (
                r["data"].get("measured_start") == reference if reference else False,
                r["data"].get("measured_start") or "",
                r["received_at"],
            ),
            default=None,
        )
        data = row["data"] if row else {}
        source_unit = data.get("unit", registry()["units"][key])
        value = data.get("value")
        if key == "weight" and row:
            value, source_unit = data.get("canonical_value"), "kg"
        result.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "unit": source_unit,
                "display_value": convert(value, selected) if source_unit == "kg" else value,
                "display_unit": selected if source_unit == "kg" else source_unit,
                "record_id": row["id"] if row else None,
                "estimated": data.get("estimated", False),
                "qualification": data.get("qualification", ""),
                "source_type": data.get("source_type"),
                "clinical_eligible": data.get("clinical_eligible", True),
                "availability": "available" if row else "not_recorded",
            }
        )
    return result
