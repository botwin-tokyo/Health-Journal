from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from access.policy import AccessDenied, AuthorizationContext
from metrics.series import definition, fingerprint
from records import service
from records.http import endpoint
from records.models import Record
from records.validation import DomainError

from .calculations import interval_total, sleep_summary, workout_day


@endpoint({"GET"})
def page(request):
    try:
        day = date.fromisoformat(request.GET.get("date", date.today().isoformat()))
    except ValueError:
        raise DomainError("invalid_date") from None
    source = request.GET.get("steps_source", "phone")
    if source not in {"phone", "ring"}:
        raise DomainError("invalid_steps_source")
    records = service.permitted(
        request,
        ["observation", "source_record"],
        request.GET.get("from", day.isoformat()),
        request.GET.get("to", day.isoformat()),
        200,
        request.GET.get("cursor"),
    )
    # A high-volume observation page must not hide a sleep/workout session.
    sessions = service.permitted(
        request, ["sleep", "workout"], day.isoformat(), day.isoformat(), 200
    )
    records["items"] += sessions["items"]
    series = {}
    sleeps = []
    workouts = []
    steps = []
    other_records = []
    for row in records["items"]:
        payload = row["data"]
        if payload.get("clinical_eligible") is False and row["kind"] not in {"sleep", "workout"}:
            other_records.append(row)
            continue
        if row["kind"] == "sleep":
            summary = None
            if payload.get("stages"):
                try:
                    summary = sleep_summary(
                        payload["measured_start"], payload["measured_end"], payload["stages"]
                    )
                except (DomainError, KeyError, TypeError, ValueError):
                    summary = None  # Preserve source data without inventing invalid stage totals.
            if summary is None and payload.get("sleep_seconds") is not None:
                summary = {
                    "known_sleep_seconds": payload["sleep_seconds"],
                    "span_seconds": (
                        datetime.fromisoformat(payload["measured_end"])
                        - datetime.fromisoformat(payload["measured_start"])
                    ).total_seconds(),
                    "stage_seconds": {},
                    "method_version": "source-reported-sleep-v1",
                }
            if summary is None:
                summary = {
                    "known_sleep_seconds": None,
                    "span_seconds": (
                        datetime.fromisoformat(payload["measured_end"])
                        - datetime.fromisoformat(payload["measured_start"])
                    ).total_seconds(),
                    "stage_seconds": {},
                    "method_version": "recorded-session-span-v1",
                }
            sleeps.append(
                {
                    **row,
                    "stage_summary": summary,
                    "display_status": "Partial session"
                    if not payload.get("complete")
                    else "Recorded session",
                }
            )
        elif row["kind"] == "workout":
            try:
                daily_duration = workout_day(payload, day)
            except (DomainError, KeyError, TypeError, ValueError):
                daily_duration = {"value": None, "absent_reason": "invalid_workout_intervals"}
            workouts.append({**row, "daily_duration": daily_duration})
        elif row["kind"] == "source_record":
            other_records.append(row)
        else:
            metric = payload.get("metric_id")
            key = fingerprint(definition(payload, metric))
            group = series.setdefault(
                key,
                {
                    "series_id": key,
                    "metric_id": metric,
                    "unit": payload.get("unit"),
                    "qualification": payload.get("qualification"),
                    "statistic": payload.get("statistic"),
                    "points": [],
                },
            )
            group["points"].append(row)
            if metric == (
                "phone_steps" if source == "phone" else "ring_step_subtotal"
            ) and payload.get("measured_end"):
                steps.append(
                    {
                        "start": payload["measured_start"],
                        "end": payload["measured_end"],
                        "count": int(payload["value"]),
                    }
                )
    from decimal import Decimal, localcontext

    from metrics.calculations import percentile
    from records.validation import derived

    for group in series.values():
        points = group["points"]
        summary = {"value": None, "absent_reason": "insufficient_coverage"}
        if (
            not records["cursor"]
            and points
            and all(row["clinical_date"] == day.isoformat() for row in points)
        ):
            values = [Decimal(row["data"]["value"]) for row in points]
            if group["metric_id"] == "bpm" and group.get("statistic") == "requested_sample":
                with localcontext() as context:
                    context.prec = 60
                    summary = {
                        "value": derived(sum(values) / len(values)),
                        "sample_count": len(values),
                        "method_version": "requested-sample-mean-v1",
                        "revision_ids": [row["revision_id"] for row in points],
                    }
            elif group["metric_id"] not in {
                "oxygen_saturation",
                "phone_steps",
                "ring_step_subtotal",
            }:
                intervals = [row["data"] for row in points]
                from .calculations import instant

                valid = all(
                    row.get("measured_start") and row.get("measured_end") for row in intervals
                )
                ordered = sorted(intervals, key=lambda row: row.get("measured_start", ""))
                valid = valid and all(
                    instant(left["measured_end"]) <= instant(right["measured_start"])
                    for left, right in zip(ordered, ordered[1:])
                )
                if valid:
                    summary = {
                        "value": derived(percentile(values, ".5")),
                        "bin_count": len(values),
                        "method_version": "daily-bin-median-v1",
                        "revision_ids": [row["revision_id"] for row in points],
                    }
        group["daily_summary"] = summary
    selected = [row for row in sleeps if row["data"].get("main_session") is True]
    sleep = selected[0] if len(selected) == 1 else None
    if not selected and sleeps:
        sleep = max(
            sleeps,
            key=lambda row: (
                bool(row["data"].get("clinical_eligible", True)),
                bool(row["data"].get("complete")),
                float((row.get("stage_summary") or {}).get("known_sleep_seconds") or 0),
                row["data"].get("measured_end", ""),
            ),
        )
    step_total = {"value": None, "absent_reason": "not_recorded"}
    if steps:
        # Every step interval must use the selected day in its recorded zone.
        zones = {
            row["data"].get("timezone")
            for row in records["items"]
            if row["data"].get("metric_id")
            == ("phone_steps" if source == "phone" else "ring_step_subtotal")
        }
        if len(zones) == 1 and None not in zones:
            zone = ZoneInfo(next(iter(zones)))
            start = datetime.combine(day, time(), zone).timestamp()
            end = datetime.combine(day + timedelta(days=1), time(), zone).timestamp()
            step_total = interval_total(steps, start, end)
        else:
            step_total = {"value": None, "absent_reason": "source_conflict"}
    from .phone_totals import daily_phone_rows, recorded_day_total

    step_records = daily_phone_rows(request, day) if source == "phone" else []
    daily_steps = recorded_day_total(step_records, day, source)
    if daily_steps is not None:
        step_total = daily_steps
    completed = [row for row in workouts if row["data"].get("state") == "completed"]
    known_durations = [
        Decimal(str(row["daily_duration"]["value"]))
        for row in completed
        if row["daily_duration"].get("value") is not None
    ]
    workout_total = (
        str(sum(known_durations, Decimal(0)))
        if completed and len(known_durations) == len(completed)
        else None
    )
    return {
        "date": day.isoformat(),
        "availability": "partial"
        if records["cursor"]
        else "available"
        if records["items"]
        else "awaiting_integration",
        "sleep": sleep,
        "sleep_sessions": sleeps,
        "sleep_absent_reason": None
        if sleep
        else "source_conflict"
        if len(selected) > 1
        else "not_recorded",
        "observation_series": list(series.values()),
        "steps": {**step_total, "source": source},
        "step_records": step_records,
        "workout_total_seconds": workout_total,
        "completed_workout_count": len(completed),
        "workouts": workouts,
        "source_records": other_records,
        "cursor": records["cursor"],
    }


@endpoint({"GET"})
def workout(request, record_id):
    row = Record.objects.filter(pk=record_id, kind="workout", deleted_at__isnull=True).first()
    if not row:
        raise AccessDenied()
    return service.dto(AuthorizationContext(request), row)
