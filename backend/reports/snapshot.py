import json

from access.policy import AccessDenied, BoundGrantContext
from django.utils import timezone
from records import service
from records.models import Record
from records.validation import DomainError


def freeze(request, draft):
    context, patient = service.owner_context(request)
    payload = service.dto(context, draft)["data"]
    audience = payload.get("grant_id")
    scoped = BoundGrantContext(context, audience) if audience else context
    epoch = scoped.epoch()
    draft_version = draft.version
    sections = []
    dependencies = []
    manifest = []
    measured = []
    for identifier in payload["record_ids"]:
        row = Record.objects.filter(pk=identifier, patient=patient, deleted_at__isnull=True).first()
        if not row or row.kind in {"draft", "snapshot", "settings", "lab_review", "import_review"}:
            raise AccessDenied()
        value = service.dto(scoped, row)
        if row.kind in {"weight", "baseline"}:
            from body.display import record as display_record

            selected_unit = payload.get("weight_unit", "kg")
            if selected_unit not in {"kg", "lb"}:
                raise DomainError("invalid_weight_unit")
            value = display_record(value, selected_unit)
        # Canonical record JSON drives both the preview and renderer. No latest reads in rendering.
        sections.append(
            {
                "heading": row.kind,
                "text": json.dumps(value["data"], ensure_ascii=False, sort_keys=True),
                "record_id": str(row.pk),
                "revision_id": str(row.current_id),
                "clinical_date": value["clinical_date"],
                "data": value["data"],
            }
        )
        dependencies.append(row.current.blob)
        manifest.append((row.pk, row.version))
        if row.current.measured_start:
            measured.append(row.current.measured_start)
    appendices = []
    import base64

    from artifacts import store
    from artifacts.models import SecureRecord
    from artifacts.selectors import select

    document_ids = payload.get("document_ids", [])
    if not isinstance(document_ids, list) or len(document_ids) > 20:
        raise DomainError("invalid_document_selection")
    total = 0
    for identifier in document_ids:
        blob = SecureRecord.objects.filter(
            object_id=identifier,
            kind="lab_document",
            owner_id=patient.owner_id,
            deleted_at__isnull=True,
        ).first()
        if blob is None:
            raise AccessDenied()
        from labs.models import LabReport

        if not LabReport.objects.filter(original=blob, parser_job__state="ready").exists():
            raise DomainError("document_not_ready", 409)
        blob, metadata, authorize = select(scoped, blob.pk, "read_original_document")
        original = store.read(blob, metadata.identity, authorize)
        total += len(original)
        if total > 12 * 1024 * 1024:
            raise DomainError("report_scope_too_large")
        appendices.append(
            {"document_id": str(blob.object_id), "pdf_base64": base64.b64encode(original).decode()}
        )
        dependencies.append(blob)
    result = {
        "template": "appointment-v2",
        "title": payload["title"],
        "sections": sections,
        "generated_at": timezone.now().isoformat(),
        "measured_through": max(measured).isoformat() if measured else None,
        "grant_id": audience,
        "schema_version": 2,
        "appendices": appendices,
        "selection": {
            "from": payload.get("from"),
            "to": payload.get("to"),
            "timezone": payload.get("timezone"),
            "weight_unit": payload.get("weight_unit", "kg"),
        },
    }

    def commit(record, revision, patient):
        from .models import DraftSnapshot

        DraftSnapshot.objects.create(draft=draft, snapshot=record)
        if scoped.epoch() != epoch or Record.objects.get(pk=draft.pk).version != draft_version:
            raise DomainError("snapshot_inputs_changed", 409)
        for identifier, version in manifest:
            if not Record.objects.filter(
                pk=identifier, version=version, deleted_at__isnull=True
            ).exists():
                raise DomainError("snapshot_inputs_changed", 409)

    return result, dependencies, audience, commit
