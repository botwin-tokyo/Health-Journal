from datetime import date

from access.policy import AccessDenied, AuthorizationContext
from records import service
from records.http import endpoint
from records.models import Record
from records.validation import DomainError, parse_json, text

from .service import validate


@endpoint({"GET", "POST", "PATCH", "DELETE"})
def records(request, kind, record_id=None):
    if request.method == "GET":
        if record_id:
            record = Record.objects.filter(pk=record_id, kind=kind).first()
            if not record:
                raise AccessDenied()
            return service.dto(AuthorizationContext(request), record)
        return service.permitted(
            request,
            [kind],
            request.GET.get("from"),
            request.GET.get("to"),
            after=request.GET.get("cursor"),
        )
    if request.method == "DELETE":
        return service.delete(request, record_id)
    body = parse_json(request.body)
    if kind == "journal" and "entry" not in body:
        body = {
            "entry": body,
            "visibility": body.get("visibility", "private"),
            "included_medication_ids": body.get("included_medication_ids", []),
            "expected_link_revisions": body.get("expected_link_revisions", {}),
        }
    if "entry" in body:
        if kind != "journal":
            raise DomainError("invalid_composite_kind")
        from .composite import prepare_composite

        payload, day, visibility, commit = prepare_composite(request, body, record_id)
        return service.save(request, kind, payload, day, record_id, visibility, commit_hook=commit)
    operations = []
    expected_links = {}
    payload, day, visibility = validate(kind, body)
    context, patient = service.owner_context(request)
    from records.components import prepare

    prepared = []
    for operation in operations:
        if operation.get("action") not in {"create", "update"}:
            raise DomainError("invalid_medication_operation")
        medication, med_day, med_visibility = validate("medication", operation["data"])
        if med_visibility != "private":
            raise DomainError("composite_medication_must_start_private")
        identifier, commit = prepare(
            context,
            patient,
            "medication",
            medication,
            med_day,
            record_id=operation.get("id"),
            expected_etag=operation.get("etag"),
        )
        prepared.append((identifier, commit))
    parent = None
    if kind == "medication" and body.get("parent_entry_id"):
        entry = Record.objects.filter(
            pk=body["parent_entry_id"], patient=patient, kind="journal", deleted_at__isnull=True
        ).first()
        if not entry:
            raise AccessDenied()
        if visibility == "shared" and entry.current.blob.visibility != "shared":
            raise DomainError("shared_entry_required")
        parent = entry.current.blob
    for target in body.get("linked_record_ids", []) + body.get("included_medication_ids", []):
        if not Record.objects.filter(pk=target, patient=patient, deleted_at__isnull=True).exists():
            raise AccessDenied()
    if (
        body.get("origin_record_id")
        and not Record.objects.filter(
            pk=body["origin_record_id"], patient=patient, deleted_at__isnull=True
        ).exists()
    ):
        raise AccessDenied()

    def commit(record, revision, patient):
        for target, expected in expected_links.items():
            linked = (
                Record.objects.select_for_update()
                .filter(pk=target, patient=patient, deleted_at__isnull=True)
                .first()
            )
            if not linked or service.etag(linked) != expected:
                raise DomainError("revision_conflict", 412)
        for _, save_medication in prepared:
            save_medication()

    return service.save(
        request, kind, payload, day, record_id, visibility, parent=parent, commit_hook=commit
    )


@endpoint({"POST"})
def search(request):
    body = parse_json(request.body)
    query = text(body.get("query"), 200, True).casefold()
    try:
        start, end = date.fromisoformat(body["from"]), date.fromisoformat(body["to"])
        if not 0 <= (end - start).days < 366:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise DomainError("invalid_date_range") from None
    page = service.permitted(request, ["journal", "question"], start, end, 128, body.get("cursor"))
    visibility = body.get("visibility")
    if visibility not in {None, "private", "shared"}:
        raise DomainError("invalid_visibility")
    rows = [
        row
        for row in page["items"]
        if (visibility is None or row["data"].get("visibility") == visibility)
        and query in (row["data"].get("title", "") + "\n" + row["data"].get("text", "")).casefold()
    ]
    return {"items": rows, "page_match_count": len(rows), "cursor": page["cursor"]}
