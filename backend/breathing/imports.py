import hashlib
import json

from access.policy import AccessDenied
from artifacts import jobs, store
from artifacts.models import SecureRecord
from artifacts.selectors import select
from crypto.envelopes import Identity, TransitKMS
from django.utils.crypto import salted_hmac
from records import service
from records.actions import Command
from records.components import prepare
from records.http import endpoint
from records.validation import DomainError, parse_json, text

from .models import MeasurementImport
from .service import manual


def etag(row):
    return '"' + salted_hmac("csv-review", f"{row.pk}:{row.version}").hexdigest() + '"'


def matching(request, row):
    if not request.headers.get("If-Match"):
        raise DomainError("precondition_required", 428)
    if request.headers["If-Match"] != etag(row):
        raise DomainError("revision_conflict", 412)


@endpoint({"POST", "GET"})
def imports(request, import_id=None):
    context, patient = service.owner_context(request)
    if request.method == "GET":
        row = (
            MeasurementImport.objects.filter(pk=import_id, patient=patient)
            .select_related("parser_job", "review")
            .first()
        )
        if not row:
            raise AccessDenied()
        result = {
            "id": str(row.pk),
            "etag": etag(row),
            "state": row.state,
            "parse_state": row.parser_job.state,
            "parse_error": row.parser_job.error_code,
            "committed_ids": row.committed_ids,
        }
        if row.parser_job.state == "ready":
            blob, metadata, authorize = select(context, row.parser_job.output_record_id)
            result["extraction"] = json.loads(store.read(blob, metadata.identity, authorize))
        if row.review_id:
            result["review"] = service.dto(context, row.review)
        return result
    command = Command(request)
    previous = command.previous()
    if previous:
        return previous
    if len(request.body) > 5 * 1024 * 1024:
        raise DomainError("csv_too_large", 413)
    if request.content_type not in {"text/csv", "application/csv"}:
        raise DomainError("csv_required", 415)
    try:
        request.body.decode("utf-8-sig")
    except UnicodeError:
        raise DomainError("invalid_csv_encoding") from None
    digest = TransitKMS().identity_digest(
        patient.owner_id, "csv", hashlib.sha256(request.body).hexdigest(), "breathing", 1
    )
    prior = MeasurementImport.objects.filter(patient=patient, content_digest=digest).first()
    if prior:
        return command.run(
            lambda: {
                "id": str(prior.pk),
                "state": prior.state,
                "etag": etag(prior),
                "duplicate": True,
            }
        )
    blob = SecureRecord(
        owner_id=patient.owner_id,
        kind="lab_document",
        category="breathing",
        clinical_date=None,
        owner_only=True,
    )
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)

    def authorize(selected, action):
        service.owner_context(request)
        return selected == identity and action == "write"

    blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
        request.body, identity, authorize
    )

    def commit():
        existing = MeasurementImport.objects.filter(patient=patient, content_digest=digest).first()
        if existing:
            return {
                "id": str(existing.pk),
                "state": existing.state,
                "etag": etag(existing),
                "duplicate": True,
            }
        blob.save()
        job = jobs.enqueue(request, blob.pk, "parse_csv")
        row = MeasurementImport.objects.create(
            patient=patient, original=blob, content_digest=digest, parser_job=job
        )
        return {"id": str(row.pk), "state": row.state, "etag": etag(row)}

    return command.run(commit)


@endpoint({"PATCH"})
def review(request, import_id):
    context, patient = service.owner_context(request)
    row = (
        MeasurementImport.objects.filter(pk=import_id, patient=patient)
        .select_related("parser_job")
        .first()
    )
    if not row:
        raise AccessDenied()
    matching(request, row)
    if row.state == "committed" or row.parser_job.state != "ready":
        raise DomainError("import_not_reviewable", 409)
    blob, metadata, authorize = select(context, row.parser_job.output_record_id)
    extracted = json.loads(store.read(blob, metadata.identity, authorize))["rows"]
    body = parse_json(request.body)
    if (
        set(body) != {"sessions", "excluded_rows", "unknown_columns_acknowledged"}
        or body["unknown_columns_acknowledged"] is not True
    ):
        raise DomainError("complete_mapping_review_required")
    if (
        not isinstance(body["sessions"], list)
        or not 1 <= len(body["sessions"]) <= 1000
        or not isinstance(body["excluded_rows"], dict)
    ):
        raise DomainError("invalid_review")
    covered = set()
    normalized = []
    for session in body["sessions"]:
        indices = session.get("source_rows")
        if not isinstance(indices, list) or not indices:
            raise DomainError("source_rows_required")
        for index in indices:
            if type(index) is not int or not 1 <= index < len(extracted) or index in covered:
                raise DomainError("ambiguous_source_rows")
            covered.add(index)
        payload, day = manual(session)
        payload.update(
            source_type="imported_file",
            source_label="MIR CSV",
            source_rows=indices,
            review_status="reviewed",
        )
        normalized.append(payload)
    for index, reason in body["excluded_rows"].items():
        index = int(index)
        text(reason, 256, True)
        if not 1 <= index < len(extracted) or index in covered:
            raise DomainError("ambiguous_source_rows")
        covered.add(index)
    if covered != set(range(1, len(extracted))):
        raise DomainError("unreviewed_source_rows")
    expected = row.version

    def commit(record, revision, patient):
        current = MeasurementImport.objects.select_for_update().get(pk=row.pk)
        if current.version != expected:
            raise DomainError("revision_conflict", 412)
        current.review = record
        current.state = "reviewed"
        current.version += 1
        current.save()

    service.save(
        request,
        "import_review",
        {
            "sessions": normalized,
            "excluded_rows": body["excluded_rows"],
            "columns": extracted[0] if extracted else [],
        },
        None,
        commit_hook=commit,
    )
    row.refresh_from_db()
    return {"id": str(row.pk), "state": row.state, "etag": etag(row)}


@endpoint({"POST"})
def commit(request, import_id):
    command = Command(request)
    previous = command.previous()
    if previous:
        return previous
    context, patient = command.context, command.patient
    row = (
        MeasurementImport.objects.filter(pk=import_id, patient=patient)
        .select_related("review__current", "parser_job")
        .first()
    )
    if not row:
        raise AccessDenied()
    matching(request, row)
    if row.state != "reviewed" or row.parser_job.state != "ready":
        raise DomainError("import_not_reviewed", 409)
    expected = row.version
    payload = service.dto(context, row.review)["data"]
    prepared = []
    from records.validation import clinical_time

    for session in payload["sessions"]:
        day, _ = clinical_time(session)
        prepared.append(
            (prepare(context, patient, "pulmonary", session, day)[1], session.get("slot"))
        )

    def apply():
        current = MeasurementImport.objects.select_for_update().get(pk=row.pk)
        if current.version != expected:
            raise DomainError("revision_conflict", 412)
        ids = []
        for save, slot in prepared:
            record = save()
            ids.append(str(record.pk))
            from .service import designate_initial

            designate_initial(record, slot)
        current.state = "committed"
        current.committed_ids = ids
        current.version += 1
        current.save()
        from django.db.models import F
        from records.models import Patient

        Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
        return {
            "id": str(current.pk),
            "state": "committed",
            "record_ids": ids,
            "etag": etag(current),
        }

    return command.run(apply)
