from access.policy import AccessDenied, AuthorizationContext
from records import service
from records.http import endpoint
from records.models import Record
from records.validation import DomainError, parse_json

from .service import manual


@endpoint({"POST"})
def create(request):
    context, patient = service.owner_context(request)
    preference = Record.objects.filter(
        patient=patient, kind="settings", deleted_at__isnull=True
    ).first()
    windows = (
        service.dto(context, preference)["data"].get("pulmonary_windows") if preference else None
    )
    payload, day = manual(parse_json(request.body), windows)
    from .service import designate_initial

    return service.save(
        request,
        "pulmonary",
        payload,
        day,
        commit_hook=lambda record, revision, patient: designate_initial(
            record, payload.get("slot")
        ),
    )


@endpoint({"GET"})
def page(request, record_id=None):
    if record_id:
        record = Record.objects.filter(pk=record_id, kind="pulmonary").first()
        if not record:
            raise AccessDenied()
        return service.dto(AuthorizationContext(request), record)
    from datetime import date

    from metrics.series import recent
    from records.models import Designation, Patient

    day = date.fromisoformat(request.GET.get("date", date.today().isoformat()))
    slot = request.GET.get("slot", "morning")
    if slot not in {"morning", "noon", "evening"}:
        raise DomainError("invalid_slot")
    context = AuthorizationContext(request)
    _, owner, grant = context.current()
    if owner is None:
        raise AccessDenied()
    patient = Patient.objects.filter(owner=owner).first()
    result = service.permitted(request, ["pulmonary"], day, day, after=request.GET.get("cursor"))
    slots = {row["data"]["slot"] for row in result["items"] if row["data"].get("slot")}
    query = Record.objects.filter(
        patient=patient,
        kind="pulmonary",
        deleted_at=None,
        superseded_at=None,
        current__blob__clinical_date=day,
    )
    allowed = grant is None or (
        "read" in grant.actions
        and "breathing" in grant.categories
        and grant.starts_on <= day <= grant.ends_on
    )
    count = query.count() if allowed else 0
    selected = None
    choice = (
        Designation.objects.filter(
            patient=patient,
            clinical_date=day,
            domain="breathing",
            slot=slot,
            record__deleted_at=None,
        )
        .select_related("record__current__blob")
        .first()
        if patient
        else None
    )
    if choice and choice.record_id:
        try:
            selected = service.dto(context, choice.record)
        except AccessDenied:
            pass
    references = (
        {metric: recent(context, patient, metric, day, slot) for metric in ["fvc", "fev1", "pef"]}
        if patient
        else {}
    )
    from datetime import timedelta

    try:
        start = date.fromisoformat(request.GET.get("from", (day - timedelta(days=27)).isoformat()))
        end = date.fromisoformat(request.GET.get("to", day.isoformat()))
        if not 0 <= (end - start).days < 366:
            raise ValueError
    except ValueError:
        raise DomainError("invalid_date_range") from None
    history = []
    if patient:
        choices = (
            Designation.objects.filter(
                patient=patient,
                domain="breathing",
                slot=slot,
                clinical_date__range=(start, end),
                record__deleted_at=None,
                record__isnull=False,
            )
            .select_related("record__current__blob")
            .order_by("clinical_date")
        )
        for choice in choices[:366]:
            try:
                history.append(service.dto(context, choice.record))
            except AccessDenied:
                continue
    result.update(
        history=history,
        date=day.isoformat(),
        slot=slot,
        minimum_sessions=1,
        saved_session_count=count,
        minimum_met=count >= 1,
        preferred_met=None if result["cursor"] else len(slots) == 3,
        slot_coverage=sorted(slots),
        coverage_complete=result["cursor"] is None,
        selected_session=selected,
        recent_baselines=references,
    )
    return result


@endpoint({"PATCH"})
def designation(request, record_id):
    context, patient = service.owner_context(request)
    row = Record.objects.filter(
        pk=record_id, patient=patient, kind="pulmonary", deleted_at__isnull=True
    ).first()
    if not row:
        raise AccessDenied()
    service.precondition(request, row)
    body = parse_json(request.body)
    if set(body) - {"slot", "make_representative", "reason"} or body.get("slot") not in {
        None,
        "morning",
        "noon",
        "evening",
    }:
        raise DomainError("invalid_designation")
    from records.validation import text

    text(body.get("reason"), 256, True)
    payload = service.dto(context, row)["data"]
    payload.update(
        slot=body["slot"], slot_override={"actor": str(request.user.pk), "reason": body["reason"]}
    )

    def commit(record, revision, patient):
        from records.models import Designation

        for previous in Designation.objects.select_for_update().filter(
            patient=patient, domain="breathing", record=record
        ):
            previous.record = None
            previous.version += 1
            previous.save()
        if body.get("make_representative") and body["slot"]:
            chosen, _ = Designation.objects.select_for_update().get_or_create(
                patient=patient,
                domain="breathing",
                clinical_date=revision.blob.clinical_date,
                slot=body["slot"],
            )
            chosen.record = record
            chosen.version += 1
            chosen.save()

    return service.save(
        request, "pulmonary", payload, row.current.blob.clinical_date, record_id, commit_hook=commit
    )
