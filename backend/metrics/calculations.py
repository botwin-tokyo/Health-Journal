from datetime import timedelta
from decimal import Decimal, localcontext

from records.validation import DomainError, derived


def percentile(values, p):
    if not values:
        return None
    with localcontext() as ctx:
        ctx.prec = 60
        values = sorted(Decimal(value) for value in values)
        h = (len(values) - 1) * Decimal(p)
        i = int(h)
        fraction = h - i
        return values[i] + fraction * (values[min(i + 1, len(values) - 1)] - values[i])


def baseline(contributors, day, kind="recent"):
    if len({row["date"] for row in contributors}) != len(contributors):
        raise DomainError("duplicate_contributor_day")
    if len({row["series_id"] for row in contributors}) > 1:
        raise DomainError("incompatible_series")
    if kind == "recent":
        rows = [r for r in contributors if day - timedelta(days=28) <= r["date"] < day]
        minimum = 14
    elif kind == "weight_mean":
        rows = [r for r in contributors if day - timedelta(days=6) <= r["date"] <= day]
        minimum = 2
    elif kind == "fixed":
        rows = contributors
        minimum = 1
    else:
        raise DomainError("invalid_baseline_kind")
    values = [Decimal(r["value"]) for r in rows]
    ready = len(values) >= minimum
    with localcontext() as ctx:
        ctx.prec = 60
        value = (
            (sum(values) / len(values) if kind == "weight_mean" else percentile(values, ".5"))
            if ready
            else None
        )
    return {
        "value": derived(value) if value is not None else None,
        "eligible": ready,
        "contributor_day_count": len(rows),
        "absent_reason": None if ready else "not_enough_eligible_data",
        "method_version": {
            "recent": "recent-median-28d-v1",
            "fixed": "fixed-median-v1",
            "weight_mean": "weight-mean-7d-v1",
        }[kind],
        "p25": derived(percentile(values, ".25")) if ready and kind != "weight_mean" else None,
        "p75": derived(percentile(values, ".75")) if ready and kind != "weight_mean" else None,
        "band_label": "Middle 50% of observed readings",
        "revision_ids": [r["revision_id"] for r in rows],
    }
