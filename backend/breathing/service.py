import uuid
from decimal import Decimal, localcontext

from records.validation import DomainError, clinical_time, decimal, derived

FIELDS = {
    "fvc": "L",
    "fev1": "L",
    "fev6": "L",
    "vext": "L",
    "fivc": "L",
    "pef": "L/min",
    "fef2575": "L/s",
    "fef25": "L/s",
    "fef50": "L/s",
    "fef75": "L/s",
    "pif": "L/s",
    "fet": "s",
    "fev1_fvc": "%",
}


def window_intervals(windows):
    import re

    result = []
    for name, pair in windows.items():
        if not isinstance(pair, list) or len(pair) != 2:
            raise DomainError("invalid_windows")
        values = []
        for value in pair:
            if not isinstance(value, str) or not re.fullmatch(
                r"(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00", value
            ):
                raise DomainError("invalid_windows")
            hour, minute = map(int, value.split(":"))
            values.append(hour * 60 + minute)
        if not values[0] < values[1]:
            raise DomainError("invalid_windows")
        result.append((values[0], values[1], name))
    result.sort()
    if any(left[1] > right[0] for left, right in zip(result, result[1:])):
        raise DomainError("overlapping_windows")
    return result


def manual(payload, windows=None):
    day, instant = clinical_time(payload)
    values = payload.get("values")
    if not isinstance(values, dict) or not values or set(values) - FIELDS.keys():
        raise DomainError("invalid_pulmonary_values")
    result = {}
    for key, value in values.items():
        if value is None:
            result[key] = None
            continue
        number = decimal(value)
        if number <= 0:
            raise DomainError("invalid_pulmonary_value")
        result[key] = value
    if not any(value is not None for value in result.values()):
        raise DomainError("empty_session")
    ratio_method = "reported"
    if result.get("fev1") and result.get("fvc") and not result.get("fev1_fvc"):
        with localcontext() as ctx:
            ctx.prec = 60
            result["fev1_fvc"] = derived(Decimal(result["fev1"]) * 100 / Decimal(result["fvc"]))
        ratio_method = "same-trial-ratio-v1"
    slot = payload.get("slot")
    if slot is None and instant:
        intervals = window_intervals(
            windows
            or {
                "morning": ["04:00", "11:00"],
                "noon": ["11:00", "16:00"],
                "evening": ["16:00", "24:00"],
            }
        )
        minute = instant.hour * 60 + instant.minute
        slot = next((name for start, end, name in intervals if start <= minute < end), None)
    if slot not in {None, "morning", "noon", "evening"}:
        raise DomainError("invalid_slot")
    fields = {
        k: payload.get(k)
        for k in [
            "clinical_date",
            "time_precision",
            "measured_start",
            "measured_end",
            "timezone",
            "original_offset_minutes",
        ]
    }
    fields.update(
        source_type="manual",
        qualification="reported",
        validity="valid",
        capture_status="not_applicable",
        slot=slot,
        selected_trial_id=str(uuid.uuid4()),
        values=result,
        units=FIELDS,
        ratio_method=ratio_method,
        curves=None,
        curve_absent_reason="not_recorded",
    )
    return fields, day


def representative(trials):
    if not trials:
        return None
    complete = [
        trial
        for trial in trials
        if trial.get("capture_status") == "complete"
        and trial.get("fvc")
        and trial.get("fev1")
        and not trial.get("corrupt")
    ]
    if not complete:
        return min(trials, key=lambda trial: (trial["sequence"], trial["id"]))
    return min(
        complete,
        key=lambda trial: (
            -(decimal(trial["fvc"]) + decimal(trial["fev1"])),
            trial["sequence"],
            trial["id"],
        ),
    )


def normalize_pef(value, unit):
    number = decimal(value)
    if number <= 0 or unit not in {"L/s", "L/min"}:
        raise DomainError("invalid_pef")
    return derived(number * 60 if unit == "L/s" else number)


def designate_initial(record, slot=None):
    from records.models import Designation

    if slot not in {"morning", "noon", "evening"}:
        return
    Designation.objects.get_or_create(
        patient=record.patient,
        clinical_date=record.current.blob.clinical_date,
        domain="breathing",
        slot=slot,
        defaults={"record": record},
    )
