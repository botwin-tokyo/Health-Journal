"""Keep authenticated source records; distinguish reported readings from retained evidence."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext

from records.validation import DomainError, clinical_time, decimal, derived

from .contract import registry, validate_item

SUPPORTED_KINDS = {
    "scalar_observation",
    "sleep_session",
    "workout",
    "pulmonary_session",
    "body_profile",
    "body_goal",
    "body_goals",
    "body_circumference",
    "circumference",
    "source_record",
}


def instant(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise DomainError("offset_required")
    return result


def stamp(data, sleep=False):
    start = instant(data["measured_start"]) if data.get("measured_start") else None
    end = instant(data["measured_end"]) if data.get("measured_end") else None
    if start and end and end <= start:
        raise DomainError("invalid_session_span")
    if start:
        data.setdefault("time_precision", "second")
        data.setdefault("original_offset_minutes", int(start.utcoffset().total_seconds() / 60))
        if not data.get("timezone"):
            data["timezone_provenance"] = "offset_only"
        else:
            data.setdefault("timezone_provenance", "source")
        # Validate the onset in its recorded offset; sleep is indexed by wake date.
        clinical_time({**data, "clinical_date": start.date().isoformat()})
        day = end.date() if sleep and end else start.date()
        data["clinical_date"] = day.isoformat()
    else:
        data.setdefault("time_precision", "day")
        day, _ = clinical_time(data)
    return day, start, end


def base_reasons(data, start, end):
    reasons = []
    source = data.get("source_type", "unknown")
    if source == "synthetic" or str(data.get("native_source", "")).upper() == "SYNTHETIC":
        reasons.append("synthetic_source")
    elif source not in registry()["source_types"] or source == "unknown":
        reasons.append("unrecognized_source")
    if data.get("qualified") is False or data.get("validity") in {
        "invalid",
        "unqualified",
        "incomplete",
        "unknown",
    }:
        reasons.append("source_unqualified")
    if any(t and t > datetime.now(timezone.utc) + timedelta(minutes=5) for t in (start, end)):
        reasons.append("future_timestamp")
    if not start and date.fromisoformat(data["clinical_date"]) > datetime.now(timezone.utc).date():
        reasons.append("future_timestamp")
    return reasons


def scalar(data, reasons):
    metric = registry()["aliases"].get(data["metric_id"], data["metric_id"])
    if metric != data["metric_id"]:
        data["original_metric_id"] = data["metric_id"]
    data["metric_id"] = metric
    number = decimal(str(data["value"]))
    data["value"] = str(number)
    expected = registry()["units"].get(metric)
    if expected == "°C" and data.get("unit") == "C":
        data["original_unit"] = "C"
        data["unit"] = "°C"
    if metric not in registry()["units"]:
        reasons.append("unrecognized_metric")
    else:
        allowed = registry()["units_compatibility"].get(metric, [expected])
        if expected == "beats/min":
            allowed = ["beats/min", "bpm"]
        if data.get("unit") not in allowed:
            raise DomainError("invalid_metric_unit")
        if data.get("unit") == "bpm":
            data.setdefault("original_unit", "bpm")
            data["unit"] = "beats/min"
        if metric == "bmi" and data.get("unit") == "":
            data["unit"] = None
        temperature = metric.startswith("skin_")
        if number < 0 and not temperature:
            reasons.append("out_of_range")
        if metric in {"weight", "fvc", "fev1", "fev6", "fev1_fvc", "pef"} and number == 0:
            reasons.append("out_of_range")
        if (data.get("unit") == "%" or metric.startswith("stress_")) and not 0 <= number <= 100:
            reasons.append("out_of_range")
    if metric in {"blood_pressure_systolic", "blood_pressure_diastolic", "blood_pressure_pulse"}:
        native = data.get("native_record", {})
        if not isinstance(native, dict):
            raise DomainError("invalid_native_record")
        if not data.get("measured_start") or data.get("timestamp_basis") != "measurement" or data.get("measurement_time_verified") is not True:
            reasons.append("measurement_time_unverified")
        if any(native.get(flag) for flag in ("bodyMovement", "cuffLoose", "irregularHeartbeat")):
            reasons.append("monitor_quality_flag")
        if number <= 0:
            reasons.append("out_of_range")
        return "blood_pressure", "sleep_activity"
    if data.get("stable") is False:
        reasons.append("unstable_measurement")
    if metric == "weight":
        with localcontext() as context:
            context.prec = 60
            kg = number if data["unit"] == "kg" else number * Decimal("0.45359237")
        data.update(canonical_value=derived(kg), canonical_unit="kg")
        return "weight", "body"
    return (
        ("body_observation", "body")
        if metric in registry()["body_metrics"]
        else ("observation", "sleep_activity")
    )


def sleep(data, start, end, reasons):
    from sleep_activity.calculations import sleep_summary

    if not data.get("complete"):
        reasons.append("partial_session")
    if data.get("sleep_seconds") is not None:
        duration = decimal(str(data["sleep_seconds"]))
        data["sleep_seconds"] = str(duration)
        if duration < 0 or duration > Decimal(str((end - start).total_seconds())):
            reasons.append("invalid_reported_duration")
    if data.get("stages"):
        try:
            sleep_summary(data["measured_start"], data["measured_end"], data["stages"])
        except DomainError:
            reasons.append("invalid_stage_intervals")
    return "sleep", "sleep_activity"


def pulmonary(data, start, reasons):
    from breathing.service import FIELDS

    trials = data.get("trials", [])
    ids = [t["trial_id"] for t in trials]
    if len(ids) != len(set(ids)):
        raise DomainError("duplicate_trial_id")
    eligible = []
    for trial in trials:
        flags = []
        instant(trial["measured_at"])
        if not trial["complete"] or trial.get("validity") in {"invalid", "unqualified"}:
            flags.append("incomplete_or_invalid_trial")
        for metric, value in trial["values"].items():
            if metric not in FIELDS:
                flags.append("unrecognized_trial_metric")
                continue
            if trial.get("units", {}).get(metric, FIELDS[metric]) != FIELDS[metric]:
                raise DomainError("invalid_trial_unit")
            if value is not None and decimal(str(value)) <= 0:
                flags.append("out_of_range")
        for key, x_unit, y_unit in [("flow_volume", "L", "L/s"), ("volume_time", "s", "L")]:
            curve = trial.get(key)
            if curve and (curve["x_unit"], curve["y_unit"]) != (x_unit, y_unit):
                raise DomainError("invalid_curve_unit")
        trial["clinical_eligible"] = not flags
        trial["evidence_reasons"] = sorted(set(flags))
        if not flags and any(v is not None for v in trial["values"].values()):
            eligible.append(trial)
    selected_id = data.get("selected_trial_id")
    selected = (
        next((t for t in eligible if t["trial_id"] == selected_id), None)
        if selected_id
        else next(iter(eligible), None)
    )
    if selected_id and selected_id not in ids:
        raise DomainError("unknown_selected_trial")
    if trials:
        data["selected_trial_id"] = selected["trial_id"] if selected else None
        data["values"] = (
            {k: str(v) if v is not None else None for k, v in selected["values"].items()}
            if selected
            else {}
        )
        data["units"] = {k: FIELDS.get(k) for k in data["values"]}
    elif not data.get("values"):
        reasons.append("no_clinical_trial")
    if data.get("status", "saved") != "saved" or (trials and not selected):
        reasons.append("incomplete_session")
    if data.get("slot") is None and start and data.get("timezone_provenance") != "offset_only":
        data["slot"] = "morning" if start.hour < 11 else "noon" if start.hour < 16 else "evening"
    return "pulmonary", "breathing"


def normalize(item):
    import copy

    # Compatibility aliases are normalized only for schema selection; original identity is unchanged.
    kind = {
        "sleep": "sleep_session",
        "weight": "scalar_observation",
        "weight_observation": "scalar_observation",
    }.get(item["kind"], item["kind"])
    from .phone_wire import adapt

    kind, data = adapt(kind, copy.deepcopy(item["payload"]))
    if item["kind"] in {"weight", "weight_observation"}:
        data.setdefault("metric_id", "weight")
    validate_item(
        {
            "source_record_id": "validation",
            "source_revision": 1,
            "operation": "upsert",
            **item,
            "kind": kind,
            "payload": data,
        }
    )
    day, start, end = stamp(data, kind == "sleep_session")
    reasons = base_reasons(data, start, end)
    if kind == "circumference":
        data["metric_id"] = "circumference_" + data["site"]
        mapped, category = scalar(data, reasons)
    elif kind == "scalar_observation":
        mapped, category = scalar(data, reasons)
    elif kind == "sleep_session":
        mapped, category = sleep(data, start, end, reasons)
    elif kind == "pulmonary_session":
        mapped, category = pulmonary(data, start, reasons)
    elif kind == "workout":
        if data["state"] != "completed" or end is None:
            reasons.append("incomplete_session")
        if data.get("clock_discontinuity"):
            reasons.append("clock_discontinuity")
        if data.get("duration_seconds") is not None and decimal(str(data["duration_seconds"])) < 0:
            reasons.append("invalid_reported_duration")
        previous = None
        for interval in data.get("intervals", []):
            left = instant(interval["start"])
            right = instant(interval["end"]) if interval.get("end") else None
            if (
                right is None
                or right <= left
                or (previous and left < previous)
                or left < start
                or (end and right > end)
            ):
                reasons.append("invalid_workout_intervals")
            previous = right or left
        mapped, category = "workout", "sleep_activity"
    else:
        reasons.append("context_evidence")
        mapped, category = (
            "body_context"
            if kind in {"body_profile", "body_goal", "circumference"}
            else "source_record",
            "body" if kind in {"body_profile", "body_goal", "circumference"} else "sleep_activity",
        )
    data["clinical_eligible"] = not reasons
    data["record_status"] = "evidence" if reasons else "clinical"
    data["evidence_reasons"] = sorted(set(reasons))
    data.setdefault("validity", "reported")
    data["availability"] = "retained_evidence" if reasons else "available"
    return mapped, category, day, data


def select_imported(record, revision, data, day):
    from records.models import Designation

    if not data.get("clinical_eligible", True):
        # A corrected formerly-selected reading can cease to be clinically eligible.
        Designation.objects.filter(record=record, automatic=True).update(record=None)
        return
    if record.kind == "weight":
        domain, slot = "body", ""
    elif record.kind == "pulmonary" and data.get("slot"):
        domain, slot = "breathing", data["slot"]
    else:
        return
    choice, created = Designation.objects.get_or_create(
        patient=record.patient,
        clinical_date=day,
        domain=domain,
        slot=slot,
        defaults={"record": record, "automatic": True},
    )
    if created or choice.record_id == record.pk:
        return
    if not choice.record_id and choice.automatic:
        choice.record = record
        choice.version += 1
        choice.save()
    elif domain == "body" and choice.automatic and choice.record_id:
        selected = choice.record.current
        if (
            revision.measured_start
            and selected.measured_start
            and revision.measured_start < selected.measured_start
        ):
            choice.record = record
            choice.version += 1
            choice.save()
