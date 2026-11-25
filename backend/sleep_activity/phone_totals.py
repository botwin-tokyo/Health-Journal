"""Use an explicitly recorded daily phone total without inventing intervals."""


def recorded_day_total(rows, day, source, partial=False):
    if source != "phone" or partial:
        return None
    totals = [
        row
        for row in rows
        if row["clinical_date"] == day.isoformat()
        and row["data"].get("metric_id") == "phone_steps"
        and row["data"].get("time_precision") == "day"
    ]
    if not totals:
        return None
    if len(totals) != 1:
        return {"value": None, "absent_reason": "source_conflict"}
    return {
        "value": totals[0]["data"]["value"],
        "method_version": "recorded-day-total-v1",
        "revision_ids": [totals[0]["revision_id"]],
    }


def daily_phone_rows(request, day):
    """Daily totals have no measurement instant; fetch them outside observation pagination."""
    from access.policy import AccessDenied, AuthorizationContext
    from records import service
    from records.models import Record

    context = AuthorizationContext(request)
    _, owner, _ = context.current()
    if owner is None:
        raise AccessDenied()
    query = Record.objects.filter(
        patient__owner=owner,
        kind="observation",
        deleted_at__isnull=True,
        superseded_at__isnull=True,
        current__measured_start__isnull=True,
        current__blob__clinical_date=day,
    ).select_related("current__blob")
    rows = []
    for record in query.iterator():
        try:
            row = service.dto(context, record)
        except AccessDenied:
            continue
        if row["data"].get("metric_id") == "phone_steps" and row["data"].get(
            "clinical_eligible", True
        ):
            rows.append(row)
    return rows
