from access.policy import AccessDenied
from artifacts import jobs
from artifacts.models import SecurityJob
from records import service
from records.http import endpoint
from records.models import Record
from records.validation import DomainError, clinical_time, parse_json, text


@endpoint({"GET", "POST", "PATCH"})
def drafts(request, record_id=None):
    context, patient = service.owner_context(request)
    if request.method == "GET":
        if not record_id:
            return service.permitted(request, ["draft"], after=request.GET.get("cursor"))
        record = Record.objects.filter(pk=record_id, patient=patient, kind="draft").first()
        if not record:
            raise AccessDenied()
        value = service.dto(context, record)
        from .models import DraftSnapshot

        frozen = (
            DraftSnapshot.objects.filter(draft=record)
            .select_related("snapshot__current__blob")
            .order_by("-created_at")
            .first()
        )
        value["outdated"] = False
        if frozen:
            dependencies = frozen.snapshot.current.blob.dependencies.all()
            for blob in dependencies:
                if not Record.objects.filter(
                    pk=blob.object_id, current__blob=blob, deleted_at__isnull=True
                ).exists():
                    value["outdated"] = True
                    break
        return value
    body = parse_json(request.body)
    text(body.get("title"), 256, True)
    selected = body.get("record_ids")
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= 100
        or len(set(selected)) != len(selected)
    ):
        raise DomainError("invalid_report_selection")
    if body.get("grant_id"):
        from access.policy import BoundGrantContext

        BoundGrantContext(context, body["grant_id"]).current()
    day, _ = clinical_time(body)
    return service.save(request, "draft", body, day, record_id)


@endpoint({"GET", "POST"})
def snapshots(request, record_id):
    from access.policy import AuthorizationContext

    if request.method == "GET":
        row = Record.objects.filter(pk=record_id, kind="snapshot", deleted_at__isnull=True).first()
        if not row:
            raise AccessDenied()
        return service.dto(AuthorizationContext(request), row)
    context, patient = service.owner_context(request)
    draft = Record.objects.filter(
        pk=record_id, patient=patient, kind="draft", deleted_at__isnull=True
    ).first()
    if not draft:
        raise AccessDenied()
    service.precondition(request, draft)
    from .snapshot import freeze

    payload, dependencies, audience, commit = freeze(request, draft)
    return service.save(
        request,
        "snapshot",
        payload,
        draft.current.blob.clinical_date,
        dependencies=dependencies,
        commit_hook=commit,
        audience_grant=audience,
    )


@endpoint({"POST"})
def export(request, record_id):
    from access.policy import AuthorizationContext

    context = AuthorizationContext(request)
    row = Record.objects.filter(pk=record_id, kind="snapshot", deleted_at__isnull=True).first()
    if not row:
        raise AccessDenied()
    service.precondition(request, row)
    service.dto(context, row)
    from accounts.policy import fresh, session_state
    from django.utils import timezone

    state = session_state(request)
    if not fresh(state):
        raise DomainError("reauthentication_required", 403)
    from artifacts.selectors import select
    from records.actions import Command

    command = Command(request, owner_only=False)

    def commit():
        pending = SecurityJob.objects.filter(
            actor=request.user,
            session_hash=state.pk,
            expires_at__gt=timezone.now(),
            input_record=row.current.blob,
            purpose="render_report",
            state__in=["queued", "running", "ready"],
        ).first()
        job = pending or jobs.enqueue(request, row.current.blob_id, "render_report")
        return {"id": str(job.pk), "state": job.state}

    return command.run(
        commit, authorize=lambda: select(context, row.current.blob_id, "download_report")
    )


@endpoint({"GET"})
def export_status(request, job_id):
    from django.utils import timezone

    from .models import ExportBundle

    bundle = ExportBundle.objects.filter(pk=job_id).first()
    if bundle:
        context, patient = service.owner_context(request)
        if bundle.owner_id != patient.owner_id:
            raise AccessDenied()
        from artifacts.selectors import select

        parts = []
        for part in bundle.parts.select_related("blob").order_by("ordinal"):
            select(context, part.blob_id, "download_report")
            parts.append(
                {"id": str(part.pk), "bytes": part.bytes, "mime_type": part.blob.mime_type}
            )
        return {
            "id": str(bundle.pk),
            "state": "expired" if bundle.expires_at <= timezone.now() else bundle.state,
            "parts": parts if bundle.state == "ready" else [],
            "error_code": bundle.error_code,
        }
    from access.policy import AuthorizationContext

    context = AuthorizationContext(request)
    job = SecurityJob.objects.filter(pk=job_id, purpose="render_report").first()
    if not job:
        raise AccessDenied()
    from artifacts.selectors import select

    select(context, job.input_record_id)
    return {
        "id": str(job.pk),
        "state": job.state,
        "error_code": job.error_code,
        "artifact_id": str(job.output_record_id) if job.state == "ready" else None,
    }
