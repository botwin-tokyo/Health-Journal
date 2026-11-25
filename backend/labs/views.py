import hashlib

from access.policy import AccessDenied, AuthorizationContext
from artifacts import jobs, store
from artifacts.models import SecureRecord
from artifacts.selectors import select
from crypto.envelopes import Identity, TransitKMS
from django.http import JsonResponse, StreamingHttpResponse
from django.utils.crypto import salted_hmac
from records import service
from records.http import endpoint
from records.models import Patient
from records.validation import DomainError, clinical_time, parse_json

from .models import LabReport
from .service import review as validate_review


def report_etag(report):
    return '"' + salted_hmac("lab-review", f"{report.pk}:{report.version}").hexdigest() + '"'


@endpoint({"POST"})
def upload(request):
    context, patient = service.owner_context(request)
    from records.actions import Command

    command = Command(request)
    previous_receipt = command.previous()
    if previous_receipt:
        return previous_receipt
    payload = request.body
    if request.content_type != "application/pdf" or not payload.startswith(b"%PDF-"):
        raise DomainError("pdf_required", 415)
    if len(payload) > 25 * 1024 * 1024:
        raise DomainError("pdf_too_large", 413)
    digest = TransitKMS().identity_digest(
        patient.owner_id, "original-pdf", hashlib.sha256(payload).hexdigest(), "labs", 1
    )
    previous = LabReport.objects.filter(patient=patient, content_digest=digest).first()
    if previous:
        return {
            "id": str(previous.pk),
            "state": previous.state,
            "duplicate": True,
            "etag": report_etag(previous),
        }
    blob = SecureRecord(
        owner_id=patient.owner_id, kind="lab_document", category="labs", clinical_date=None
    )
    identity = Identity(patient.owner_id, blob.kind, blob.object_id, blob.pk, 1)

    def authorize(selected, action):
        service.owner_context(request)
        return identity == selected and action == "write"

    blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
        payload, identity, authorize
    )

    def commit():
        previous = LabReport.objects.filter(patient=patient, content_digest=digest).first()
        if previous:
            return {
                "id": str(previous.pk),
                "state": previous.state,
                "duplicate": True,
                "etag": report_etag(previous),
            }
        blob.save()
        job = jobs.enqueue(request, blob.pk, "parse_pdf")
        report = LabReport.objects.create(
            patient=patient, original=blob, content_digest=digest, parser_job=job
        )
        return {"id": str(report.pk), "state": report.state, "etag": report_etag(report)}

    return JsonResponse(command.run(commit), status=202)


@endpoint({"GET"})
def reports(request, report_id=None):
    context = AuthorizationContext(request)
    _, owner, grant = context.current()
    if not owner:
        raise AccessDenied()
    patient = Patient.objects.filter(owner=owner).first()
    if grant:
        from .models import PublishedResult

        query = PublishedResult.objects.filter(
            report__patient=patient, record__deleted_at__isnull=True
        )
        if report_id:
            query = query.filter(report_id=report_id)
        else:
            query = query.filter(superseded_at__isnull=True)
        grouped = {}
        for result in query.select_related("record__current__blob", "report__original")[:200]:
            try:
                value = service.dto(context, result.record)
            except AccessDenied:
                continue
            entry = grouped.setdefault(
                str(result.report_id),
                {"id": str(result.report_id), "results": [], "state": "reviewed"},
            )
            entry["results"].append(value)
            if (
                str(result.report.original.object_id) in grant.whole_document_ids
                and "read_original_document" in grant.actions
            ):
                entry["document_id"] = str(result.report.original.object_id)
        if report_id:
            if str(report_id) not in grouped:
                raise AccessDenied()
            return grouped[str(report_id)]
        return {"items": list(grouped.values())}
    _, patient = service.owner_context(request)
    query = LabReport.objects.filter(patient=patient).select_related("parser_job", "review")

    def result(report):
        job = report.parser_job
        extraction = None
        if report_id and job and job.state == "ready" and job.output_record_id:
            import json

            extracted, metadata, authorize = select(context, job.output_record_id)
            extraction = json.loads(store.read(extracted, metadata.identity, authorize))
        return {
            "extraction": extraction,
            "id": str(report.pk),
            "document_id": str(report.original.object_id),
            "etag": report_etag(report),
            "state": report.state,
            "parse_state": job.state if job else "not_requested",
            "parse_error": job.error_code if job else None,
            "review": service.dto(AuthorizationContext(request), report.review)
            if report.review_id
            else None,
        }

    if report_id:
        row = query.filter(pk=report_id).first()
        if not row:
            raise AccessDenied()
        return result(row)
    return {"items": [result(row) for row in query.order_by("-created_at")[:50]]}


@endpoint({"PATCH"})
def review(request, report_id):
    previous = service.replay(request)
    _, patient = service.owner_context(request)
    report = LabReport.objects.filter(pk=report_id, patient=patient).first()
    if not report:
        raise AccessDenied()
    if previous is not None:
        return {
            "id": str(report.pk),
            "etag": report_etag(report),
            "state": report.state,
            "review": previous,
        }
    if not request.headers.get("If-Match"):
        raise DomainError("precondition_required", 428)
    expected = report_etag(report)
    if request.headers["If-Match"] != expected:
        raise DomainError("revision_conflict", 412)
    body = validate_review(parse_json(request.body))
    day, _ = clinical_time(body, allow_unknown=True)

    # Each draft is immutable evidence. Publication is a separate explicit action.
    def commit(record, revision, patient):
        current = LabReport.objects.select_for_update().get(pk=report.pk)
        if report_etag(current) != expected:
            raise DomainError("revision_conflict", 412)
        current.review = record
        current.version += 1
        current.state = "needs_review"
        current.save()

    result = service.save(request, "lab_review", body, day, commit_hook=commit)
    report.refresh_from_db()
    return {
        "id": str(report.pk),
        "etag": report_etag(report),
        "state": report.state,
        "review": result,
    }


@endpoint({"GET"})
def document(request, document_id):
    context = AuthorizationContext(request)
    blob = SecureRecord.objects.filter(
        object_id=document_id, kind="lab_document", deleted_at__isnull=True
    ).first()
    if not blob:
        raise AccessDenied()
    # Only successfully parsed originals may be viewed; hostile originals remain quarantine.
    report = LabReport.objects.filter(original=blob, parser_job__state="ready").first()
    if not report:
        raise DomainError("document_not_ready", 409)
    blob, metadata, authorize = select(context, blob.pk, "read_original_document")
    payload = store.read(blob, metadata.identity, authorize)
    epoch = context.epoch()
    start, end = 0, len(payload) - 1
    range_header = request.headers.get("Range")
    if range_header:
        import re

        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        if not match or not any(match.groups()):
            raise DomainError("invalid_range", 416)
        left, right = match.groups()
        if left:
            start = int(left)
            end = min(int(right), end) if right else end
        else:
            count = int(right)
            if count <= 0:
                raise DomainError("invalid_range", 416)
            start = max(0, len(payload) - count)
        if start > end or start >= len(payload):
            raise DomainError("invalid_range", 416)

    def chunks():
        for index in range(start, end + 1, 65536):
            try:
                if context.epoch() != epoch:
                    return
                select(context, blob.pk, "read_original_document")
            except AccessDenied:
                return
            yield payload[index : min(index + 65536, end + 1)]

    response = StreamingHttpResponse(
        chunks(), content_type="application/pdf", status=206 if range_header else 200
    )
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(end - start + 1)
    if range_header:
        response["Content-Range"] = f"bytes {start}-{end}/{len(payload)}"
    response["Content-Disposition"] = 'attachment; filename="laboratory.pdf"'
    return response


@endpoint({"POST"})
def publish(request, report_id):
    context, patient = service.owner_context(request)
    from records.actions import Command

    command = Command(request)
    previous = command.previous()
    if previous:
        return previous
    report = (
        LabReport.objects.filter(pk=report_id, patient=patient)
        .select_related("review__current", "parser_job")
        .first()
    )
    if not report or not report.review_id:
        raise AccessDenied()
    if not request.headers.get("If-Match"):
        raise DomainError("precondition_required", 428)
    expected = report_etag(report)
    if request.headers["If-Match"] != expected:
        raise DomainError("revision_conflict", 412)
    if report.state != "needs_review" or report.parser_job.state not in {"ready","failed"}:
        raise DomainError("report_not_ready", 409)
    payload = validate_review(service.dto(context, report.review)["data"])
    if (
        report.parser_job.state != "ready"
        and not payload.get("document_only")
        and payload.get("manual_transcription_confirmed") is not True
    ):
        raise DomainError("report_not_ready", 409)
    from records.components import prepare

    from .models import PublishedResult
    from .service import analyte_series

    prepared = []
    for row in [] if payload.get("document_only") else payload.get("results", []):
        if row.get("excluded"):
            continue
        result = {
            **row,
            "clinical_date": payload.get("clinical_date"),
            "time_precision": payload.get("time_precision", "unknown"),
            "source_type": "imported_file",
            "qualification": "reported",
            "validity": "valid",
            "review_status": "reviewed",
            "source_report_status": payload["source_report_status"],
            "transcription_method": "manual"
            if payload.get("manual_transcription_confirmed")
            else "extraction_review",
        }
        day, _ = clinical_time(result, allow_unknown=True)
        _, commit = prepare(context, patient, "lab", result, day)
        prepared.append((commit, analyte_series(result)))

    def publish_commit():
        current = LabReport.objects.select_for_update().get(pk=report.pk)
        if report_etag(current) != expected:
            raise DomainError("revision_conflict", 412)
        from django.utils import timezone
        from records.models import Record

        prior_report = payload.get("supersedes_report_id")
        previous_ids = [current.pk]
        if prior_report:
            older = (
                LabReport.objects.select_for_update()
                .filter(pk=prior_report, patient=patient, state__in=["reviewed", "document_only"])
                .first()
            )
            if not older or older.pk == current.pk or older.created_at >= current.created_at:
                raise DomainError("invalid_report_supersession")
            current.supersedes = older
            previous_ids.append(older.pk)
        prior = PublishedResult.objects.filter(
            report_id__in=previous_ids, superseded_at__isnull=True
        )
        Record.objects.filter(pk__in=prior.values("record_id")).update(superseded_at=timezone.now())
        prior.update(superseded_at=timezone.now())
        for commit, series_id in prepared:
            result = commit()
            PublishedResult.objects.create(
                report=current,
                record=result,
                review_revision=report.review.current,
                series_id=series_id,
            )
        current.state = "document_only" if payload.get("document_only") else "reviewed"
        current.version += 1
        current.save()
        from django.db.models import F

        Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
        from operations import audit

        audit.emit("lab_published", request.user, current.pk)
        return {"id": str(report.pk), "state": current.state, "etag": report_etag(current)}

    return command.run(publish_commit)


@endpoint({"GET"})
def trends(request):
    result = service.permitted(
        request,
        ["lab"],
        request.GET.get("from"),
        request.GET.get("to"),
        after=request.GET.get("cursor"),
    )
    from .service import analyte_series

    selected = request.GET.get("series_id")
    groups = {}
    for row in result["items"]:
        series = analyte_series(row["data"])
        if selected and selected != series:
            continue
        group = groups.setdefault(
            series, {"series_id": series, "unit": row["data"].get("unit"), "points": []}
        )
        group["points"].append(
            {
                **row,
                "plot_kind": "bound"
                if row["data"].get("operator") in {"lt", "le", "gt", "ge"}
                else "point"
                if row["data"].get("value_kind") == "numeric"
                else "text",
            }
        )
    return {"series": list(groups.values()), "cursor": result["cursor"]}
