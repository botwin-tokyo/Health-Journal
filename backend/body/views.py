from datetime import date, timedelta

from access.policy import AccessDenied, AuthorizationContext
from django.db.models import F
from records import service
from records.http import endpoint
from records.models import Designation, Patient, Record
from records.validation import DomainError, parse_json

from .service import day_etag, designate, save_weight


@endpoint({"GET", "POST", "PATCH", "DELETE"})
def weights(request, record_id=None):
    if request.method == "GET":
        record = Record.objects.filter(pk=record_id, kind="weight").first()
        if not record:
            raise AccessDenied()
        return service.dto(AuthorizationContext(request), record)
    if request.method == "DELETE":
        return service.delete(request, record_id)
    return save_weight(request, parse_json(request.body), record_id)


@endpoint({"GET"})
def page(request):
    try:
        day = date.fromisoformat(request.GET.get("date", date.today().isoformat()))
        start = date.fromisoformat(request.GET.get("from", (day - timedelta(days=27)).isoformat()))
        end = date.fromisoformat(request.GET.get("to", day.isoformat()))
        if not 0 <= (end - start).days < 366:
            raise ValueError
    except ValueError:
        raise DomainError("invalid_date_range") from None
    result = service.permitted(request, ["weight"], start, end, after=request.GET.get("cursor"))
    ctx = AuthorizationContext(request)
    user, owner, grant = ctx.current()
    patient = Patient.objects.filter(owner=owner).first()
    if patient is None:
        from types import SimpleNamespace

        patient = SimpleNamespace(pk=None, owner_id=owner.pk)
    result.update(
        date=day.isoformat(),
        representative_etag=day_etag(patient, day) if patient and not grant else None,
    )
    from metrics.calculations import baseline

    selected = (
        Designation.objects.filter(
            patient_id=patient.pk,
            domain="body",
            clinical_date__range=(day - timedelta(days=6), day),
            record__deleted_at__isnull=True,
            record__isnull=False,
        ).select_related("record__current__blob")
        if patient.pk
        else []
    )
    contributors = []
    result["representative_id"] = None
    try:
        for row in selected:
            value = service.dto(ctx, row.record)
            contributors.append(
                {
                    "date": row.clinical_date,
                    "series_id": __import__("metrics.series", fromlist=["fingerprint"]).fingerprint(
                        __import__("metrics.series", fromlist=["definition"]).definition(
                            value["data"], "weight"
                        )
                    ),
                    "value": value["data"]["canonical_value"],
                    "revision_id": value["revision_id"],
                }
            )
            if row.clinical_date == day:
                result["representative_id"] = str(row.record_id)
                result["representative_record"] = value
        result["seven_day_mean"] = baseline(contributors, day, "weight_mean")
    except DomainError as error:
        if error.code != "incompatible_series":
            raise
        result["seven_day_mean"] = {"value": None, "absent_reason": "source_conflict"}
    except AccessDenied:
        result["seven_day_mean"] = {"value": None, "absent_reason": "not_in_shared_scope"}

    from metrics.series import recent

    result["recent_baseline"] = (
        recent(ctx, patient, "weight", day)
        if patient.pk
        else {"value": None, "absent_reason": "not_enough_eligible_data"}
    )
    from .composition import cards

    result["composition"] = cards(request, day, result.get("representative_record"))
    from .display import aggregate, unit
    from .display import record as display_record

    selected_unit = unit(request)
    result["items"] = [display_record(item, selected_unit) for item in result["items"]]
    if result.get("representative_record"):
        result["representative_record"] = display_record(result["representative_record"], selected_unit)
    from metrics.aggregates import read

    cached = read(ctx, patient, "weight", day, "weight_mean") if patient.pk else None
    if cached is not None:
        result["seven_day_mean"] = cached
    result["seven_day_mean"] = aggregate(result["seven_day_mean"], selected_unit)
    result["recent_baseline"] = aggregate(result["recent_baseline"], selected_unit)
    reference = result["recent_baseline"]
    if request.GET.get("baseline_id"):
        fixed = Record.objects.filter(pk=request.GET["baseline_id"], kind="baseline").first()
        try:
            if fixed is None:
                raise AccessDenied()
            reference = service.dto(ctx, fixed)["data"]
            if reference.get("metric_id") != "weight":
                raise DomainError("incompatible_reference")
        except AccessDenied:
            reference = {"value": None, "absent_reason": "not_in_shared_scope"}
    from .display import comparison

    result["delta"] = comparison(ctx, patient, day, reference, selected_unit)
    return result


@endpoint({"PUT"})
def representative(request, day):
    _, patient = service.owner_context(request)
    try:
        day = date.fromisoformat(day)
    except ValueError:
        raise DomainError("invalid_date") from None
    body = parse_json(request.body)
    from records.actions import Command

    command = Command(request)

    def commit():
        record = (
            Record.objects.filter(pk=body.get("record_id"), patient=patient).first()
            if body.get("record_id")
            else None
        )
        if body.get("record_id") and not record:
            raise AccessDenied()
        value = designate(patient, day, record, request.headers.get("If-Match"))
        Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
        from jobs.service import enqueue

        if record:
            enqueue("invalidate", record.pk, Patient.objects.get(pk=patient.pk).source_epoch)
        return {"record_id": str(record.pk) if record else None, "etag": value}

    return command.run(commit)
