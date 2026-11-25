"""Translate the already-shipped mobile app wire format on the server.

Original native_record is retained.
"""

import copy
from datetime import datetime, timezone
from decimal import Decimal

from records.validation import DomainError


def timestamp(value):
    return datetime.fromtimestamp(int(value) / 1000, timezone.utc).isoformat()


def number(value):
    return None if value is None else format(Decimal(str(value)), "f")


def iso(value):
    try:
        return datetime.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise DomainError("invalid_clinical_time") from None


def adapt(kind, payload):
    data = copy.deepcopy(payload)
    # java.time.OffsetDateTime.toString omits zero seconds; normalize only display times.
    for key in ("measured_start", "measured_end", "received_at", "updated_at"):
        if data.get(key):
            data[key] = iso(data[key])
    for row in data.get("stages", []):
        for key in ("start", "end"):
            row[key] = iso(row[key])
    native = data.get("native_record")
    native = native if isinstance(native, dict) else {}
    mapped = {"body_goals": "body_goal", "body_circumference": "circumference"}.get(kind, kind)
    if mapped == "body_profile":
        for target, source in [
            ("profile_id", "id"),
            ("revision", "revision"),
            ("height_cm", "heightCm"),
            ("birth_date", "birthDate"),
            ("name", "name"),
            ("sex", "sex"),
            ("athlete", "athlete"),
        ]:
            if source in native:
                data.setdefault(
                    target, number(native[source]) if target == "height_cm" else native[source]
                )
    elif mapped == "body_goal":
        for target, source in [
            ("profile_id", "profileId"),
            ("weight_kg", "weightKg"),
            ("body_fat_percent", "fatPercent"),
        ]:
            if source in native:
                data.setdefault(
                    target, native[source] if target == "profile_id" else number(native[source])
                )
    elif mapped == "circumference":
        for target, source in [
            ("profile_id", "profileId"),
            ("site", "site"),
            ("value", "cm"),
            ("notes", "notes"),
        ]:
            if source in native:
                data.setdefault(
                    target, number(native[source]) if target == "value" else native[source]
                )
        data.setdefault("unit", "cm")
    elif mapped == "sleep_session":
        for target, source in [
            ("stage_algorithm", "stageAlgorithm"),
            ("firmware", "firmware"),
            ("acquisition", "acquisition"),
            ("native_source", "source"),
        ]:
            if source in native:
                data.setdefault(target, native[source])
        if native.get("receivedAt") is not None:
            data.setdefault("received_at", timestamp(native["receivedAt"]))
    elif mapped == "pulmonary_session":
        if "status" in data:
            data.setdefault("source_status", data["status"])
            data["status"] = data["status"].lower()
        for target, source in [
            ("title", "title"),
            ("notes", "notes"),
            ("tags", "tags"),
            ("context_history", "contextHistory"),
            ("native_source", "source"),
        ]:
            if source in native:
                data.setdefault(target, native[source])
        if native.get("updatedAt") is not None:
            data.setdefault("updated_at", timestamp(native["updatedAt"]))
        if "trials" not in data and isinstance(native.get("trials"), list):
            trials = []
            for trial in native["trials"]:
                row = {
                    "trial_id": trial["id"],
                    "measured_at": timestamp(trial["at"]),
                    "values": {
                        key: number(value) for key, value in trial.get("metrics", {}).items()
                    },
                    "complete": trial.get("complete", True),
                    "quality": trial.get("quality", ""),
                    "warnings": trial.get("warnings", []),
                    "notes": trial.get("notes", ""),
                }
                for target, source, x, y in [
                    ("flow_volume", "flowVolume", "L", "L/s"),
                    ("volume_time", "volumeTime", "s", "L"),
                ]:
                    if source in trial:
                        row[target] = {
                            "x_unit": x,
                            "y_unit": y,
                            "points": [
                                {"x": number(p["x"]), "y": number(p["y"])} for p in trial[source]
                            ],
                        }
                if "rawPackets" in trial:
                    row["raw_packets"] = trial["rawPackets"]
                trials.append(row)
            data["trials"] = trials
            complete = [t for t in trials if t["complete"]]
            selected = max(
                complete,
                key=lambda t: sum(Decimal(t["values"].get(k) or "0") for k in ["fvc", "fev1"]),
                default=None,
            )
            if selected:
                data.setdefault("selected_trial_id", selected["trial_id"])
        # Early shipped sessions had only selected values in the parent. Keep these usable.
        if "trials" not in data and isinstance(data.get("values"), dict):
            data["trials"] = []
    elif mapped == "workout":
        details = native.get("details") if isinstance(native.get("details"), dict) else {}
        data.setdefault("details", details)
        for target, source in [("notes", "notes"), ("version", "version")]:
            if source in native:
                data.setdefault(target, native[source])
        for target, source in [
            ("routine_snapshot", "snapshot"),
            ("sets", "sets"),
            ("route_points", "route"),
            ("calories", "estimate"),
        ]:
            if source in details:
                data.setdefault(target, details[source])
        if "intervals" not in data and details.get("intervals"):
            data["intervals"] = [
                {
                    "start": timestamp(row["wallStart"]),
                    "end": timestamp(row["wallEnd"]) if row.get("wallEnd") is not None else None,
                    "kind": row["kind"].lower(),
                }
                for row in details["intervals"]
            ]
    return mapped, data


def compact_assets(data):
    """Keep chunked originals downloadable without duplicating huge blobs into a record."""
    if not data.get("native_record_assets"):
        return data
    data.pop("native_record", None)
    ids = data["native_record_assets"]["ids"]
    for trial in data.get("trials", []):
        for key in ("flow_volume", "volume_time", "raw_packets"):
            trial.pop(key, None)
        trial["asset_ids"] = ids
        trial["curve_storage"] = "attached_native_record"
    for key in ("details", "routine_snapshot", "sets", "route_points"):
        data.pop(key, None)
    data["native_fields_in_assets"] = True
    return data
