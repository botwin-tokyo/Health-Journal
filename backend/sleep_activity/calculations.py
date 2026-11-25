import math
from datetime import datetime
from decimal import Decimal, localcontext

from records.validation import DomainError, decimal, derived


def instant(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise DomainError("offset_required")
    return result.timestamp()


def sleep_summary(start, end, stages):
    start, end = instant(start), instant(end)
    if end <= start:
        raise DomainError("invalid_sleep_span")
    rows = sorted([(instant(row["start"]), instant(row["end"]), row["stage"]) for row in stages])
    totals = {key: 0 for key in ["light", "deep", "rem", "awake", "unknown"]}
    previous = start
    merged = []
    for left, right, stage in rows:
        if stage not in totals or left < previous or right <= left or right > end:
            raise DomainError("invalid_stage_interval")
        if left > previous:
            merged.append((previous, left, "unknown"))
        if merged and merged[-1][2] == stage and merged[-1][1] == left:
            merged[-1] = (merged[-1][0], right, stage)
        else:
            merged.append((left, right, stage))
        previous = right
    if previous < end:
        merged.append((previous, end, "unknown"))
    for left, right, stage in merged:
        totals[stage] += right - left
    awakenings = sum(
        1
        for i, (left, right, stage) in enumerate(merged)
        if stage == "awake"
        and right - left >= 60
        and 0 < i < len(merged) - 1
        and merged[i - 1][2] in {"light", "deep", "rem"}
        and merged[i + 1][2] in {"light", "deep", "rem"}
    )
    return {
        "span_seconds": end - start,
        "stage_seconds": totals,
        "known_sleep_seconds": sum(totals[k] for k in ["light", "deep", "rem"]),
        "observed_awakenings": awakenings,
        "method_version": "stage-interval-v1",
    }


def clock_variation(seconds):
    if len(seconds) < 2:
        return None
    angles = [value * 2 * math.pi / 86400 for value in seconds]
    x = sum(math.cos(a) for a in angles) / len(angles)
    y = sum(math.sin(a) for a in angles) / len(angles)
    if math.hypot(x, y) <= 1e-12:
        return None
    mean = math.atan2(y, x)
    return (
        sum(abs((a - mean + math.pi) % (2 * math.pi) - math.pi) for a in angles)
        / len(angles)
        * 1440
        / (2 * math.pi)
    )


def calories(method, weight, minutes=None, met=None, distance=None):
    with localcontext() as ctx:
        ctx.prec = 60
        kg = decimal(weight)
        if kg <= 0:
            raise DomainError("invalid_weight")
        if method in {"met-gross-v1", "met-active-v1"}:
            effort, duration = decimal(met), decimal(minutes)
            if effort < 1 or duration < 0:
                raise DomainError("invalid_energy_inputs")
            result = (
                (effort - (1 if method == "met-active-v1" else 0))
                * Decimal("3.5")
                * kg
                * duration
                / 200
            )
        elif method == "argus-running-v1":
            km = decimal(distance)
            if km < 0:
                raise DomainError("invalid_energy_inputs")
            result = (Decimal(".95") * kg + Decimal(".84")) * km * Decimal("1.07")
        else:
            raise DomainError("unsupported_energy_method")
        return derived(result)


def interval_total(rows, start, end, value_key="count"):
    """Exclude both sides of unresolved overlaps; never prorate recorded counts."""
    contained = []
    excluded = 0
    for row in rows:
        left, right = instant(row["start"]), instant(row["end"])
        if left < start or right > end or right <= left:
            excluded += 1
            continue
        value = row[value_key]
        if type(value) is not int or value < 0:
            raise DomainError("invalid_interval_count")
        contained.append((left, right, value))
    conflicts = set()
    for i, (left, right, _) in enumerate(contained):
        for j, (other_left, other_right, _) in enumerate(contained[:i]):
            if left < other_right and other_left < right:
                conflicts.update((i, j))
    accepted = [row for i, row in enumerate(contained) if i not in conflicts]
    return {
        "value": sum(row[2] for row in accepted) if accepted else None,
        "covered_seconds": sum(row[1] - row[0] for row in accepted),
        "excluded_intervals": excluded + len(conflicts),
        "absent_reason": None if accepted else "insufficient_coverage",
    }


def workout_day(payload, day):
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    if payload.get("state") != "completed" or payload.get("clock_discontinuity"):
        return {
            "value": None,
            "absent_reason": "clock_discontinuity"
            if payload.get("clock_discontinuity")
            else "capture_incomplete",
        }
    if (
        not payload.get("intervals") or payload.get("timezone_provenance") == "offset_only"
    ) and payload.get("duration_seconds") is not None:
        return {
            "value": str(payload["duration_seconds"]),
            "unit": "s",
            "method_version": "source-recorded-duration-v1",
            "absent_reason": None,
        }
    if payload.get("timezone_provenance") == "offset_only":
        return {"value": None, "absent_reason": "source_unavailable"}
    zone = ZoneInfo(payload["timezone"])
    start = datetime.combine(day, time(), zone).timestamp()
    end = datetime.combine(day + timedelta(days=1), time(), zone).timestamp()
    previous = None
    duration = work = 0
    for row in sorted(payload.get("intervals", []), key=lambda x: x["start"]):
        left, right = instant(row["start"]), instant(row["end"])
        if right <= left or (previous is not None and left < previous):
            raise DomainError("invalid_workout_interval")
        previous = right
        if row["kind"] not in {"work", "rest", "pause"}:
            raise DomainError("invalid_workout_interval")
        clipped = max(0, min(end, right) - max(start, left))
        if row["kind"] != "pause":
            duration += clipped
        if row["kind"] == "work":
            work += clipped
    return {
        "value": str(duration),
        "work_seconds": str(work),
        "unit": "s",
        "method_version": "completed-work-rest-v1",
        "absent_reason": None,
    }
