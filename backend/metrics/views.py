import json
from datetime import date

from access.policy import AccessDenied, AuthorizationContext
from django.utils.crypto import salted_hmac
from records import service
from records.http import endpoint
from records.models import Patient, Record
from records.validation import DomainError, parse_json

from .calculations import baseline
from .registry import capability_rows


@endpoint({"GET"})
def catalog(request):
    return {"registry_version": "health03-metrics-1", "metrics": capability_rows()}


def compute(request, body):
    context, patient = service.owner_context(request)
    metric = body.get("metric_id")
    if metric not in {"weight", "fvc", "fev1", "fev6", "pef", "fef2575", "fet"}:
        raise DomainError("baseline_metric_not_available")
    try:
        start, end = date.fromisoformat(body["from"]), date.fromisoformat(body["to"])
        if not 0 <= (end - start).days < 366:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        raise DomainError("invalid_date_range") from None
    epoch = Patient.objects.get(pk=patient.pk).source_epoch
    from .series import contributors

    rows, deps, definitions = contributors(
        context, patient, metric, start, end, body.get("slot"), body.get("series_id")
    )
    if len(deps) > 128:
        raise DomainError("baseline_scope_too_large")
    result = baseline(rows, end, "fixed")
    result.update(
        metric_id=metric,
        unit="kg"
        if metric == "weight"
        else __import__("breathing.service", fromlist=["FIELDS"]).FIELDS[metric],
        series_id=rows[0]["series_id"] if rows else body.get("series_id"),
        series_definition=definitions.get(rows[0]["series_id"]) if rows else None,
        slot=body.get("slot"),
        from_date=start.isoformat(),
        to_date=end.isoformat(),
        source_epoch=epoch,
    )
    fingerprint = salted_hmac(
        "baseline-preview", str(patient.pk) + json.dumps(result, sort_keys=True)
    ).hexdigest()
    result["preview_fingerprint"] = fingerprint
    if metric == "weight":
        from body.display import aggregate

        display_unit = body.get("weight_unit", "kg")
        if display_unit not in {"kg", "lb"}:
            raise DomainError("invalid_weight_unit")
        result = aggregate(result, display_unit)
    return result, deps, end, epoch


@endpoint({"POST"})
def preview(request):
    return compute(request, parse_json(request.body))[0]


@endpoint({"GET", "POST"})
def references(request, record_id=None):
    if request.method == "GET":
        if record_id:
            row = Record.objects.filter(pk=record_id, kind="baseline").first()
            if not row:
                raise AccessDenied()
            from body.display import record as display_record
            from body.display import unit

            return display_record(service.dto(AuthorizationContext(request), row), unit(request))
        from body.display import record as display_record
        from body.display import unit

        result = service.permitted(request, ["baseline"], after=request.GET.get("cursor"))
        selected_unit = unit(request)
        result["items"] = [display_record(row, selected_unit) for row in result["items"]]
        return result
    previous = service.replay(request)
    if previous is not None:
        return previous
    body = parse_json(request.body)
    result, deps, day, epoch = compute(request, body)
    if not result["eligible"]:
        raise DomainError("not_enough_eligible_data")
    if (
        body.get("source_epoch") != epoch
        or body.get("preview_fingerprint") != result["preview_fingerprint"]
    ):
        raise DomainError("baseline_preview_changed", 409)

    def commit(record, revision, patient):
        if patient.source_epoch != epoch:
            raise DomainError("baseline_preview_changed", 409)

    return service.save(request, "baseline", result, day, dependencies=deps, commit_hook=commit)


@endpoint({"GET"})
def overview(request):
    import json

    from body.views import page as body_page
    from breathing.views import page as breathing_page
    from sleep_activity.views import page as sleep_page

    results = []
    for view in (body_page, breathing_page, sleep_page):
        selected_query = request.GET
        if view is sleep_page:
            request.GET = selected_query.copy()
            request.GET.pop("from", None)
            request.GET.pop("to", None)
        try:
            response = view(request)
        finally:
            request.GET = selected_query
        if response.status_code != 200:
            return response
        results.append(json.loads(response.content))
    body, breathing, sleep = results
    return {
        "body": body,
        "breathing": breathing,
        "sleep_activity": sleep,
        "records": service.permitted(
            request,
            ["weight", "pulmonary", "lab"],
            request.GET.get("date"),
            request.GET.get("date"),
        ),
        "calculation_state": "current_authorized_inputs",
    }


@endpoint({"GET"})
def sleep_activity(request):
    return {
        "availability": "awaiting_integration",
        "absent_reason": "awaiting_integration",
        "observation_series": [],
        "sleep": None,
        "steps": None,
        "workouts": [],
        "source_capabilities": [
            r for r in capability_rows() if r["capability_status"] != "implemented"
        ],
    }


@endpoint({"POST"})
def retire(request, record_id):
    from records.actions import Command

    command = Command(request)

    def commit():
        record = (
            Record.objects.select_for_update()
            .filter(pk=record_id, patient=command.patient, kind="baseline", deleted_at__isnull=True)
            .first()
        )
        if not record:
            raise AccessDenied()
        service.precondition(request, record)
        from .models import RetiredReference

        RetiredReference.objects.get_or_create(record=record)
        return {"id": str(record.pk), "status": "retired"}

    return command.run(commit)
