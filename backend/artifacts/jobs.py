import json
import threading
import uuid
from datetime import timedelta

from access.policy import AccessDenied, AuthorizationContext, JobAuthorizationContext
from accounts.policy import fresh, session_state
from crypto.envelopes import Identity, KMSUnavailable
from django.db import connections, transaction
from django.utils import timezone
from parser_service.protocol import invoke

from . import store
from .models import SecureRecord, SecurityJob
from .selectors import select

PURPOSES = {"parse_pdf", "parse_csv", "render_report"}


def enqueue(request, record_id, purpose):
    if purpose not in PURPOSES:
        raise ValueError("Unsupported job purpose")
    state = session_state(request)
    context = AuthorizationContext(request)
    action = "download_report" if purpose == "render_report" else "read_original_document"
    if state is None or (purpose == "render_report" and not fresh(state)):
        raise AccessDenied()
    if purpose != "render_report" and request.user.role != "owner":
        raise AccessDenied()
    record, _, _ = select(context, record_id, action)
    if record.audience_grant:
        from access.policy import BoundGrantContext

        context = BoundGrantContext(context, record.audience_grant)
    return SecurityJob.objects.create(
        owner=record.owner,
        actor=request.user,
        purpose=purpose,
        session_hash=state.pk,
        grant_id=record.audience_grant or request.session.get("active_grant_id"),
        permission_epoch=context.epoch(),
        input_record=record,
        expires_at=timezone.now() + timedelta(hours=24),
    )


@transaction.atomic
def claim():
    now = timezone.now()
    SecurityJob.objects.filter(state="running", lease_until__lte=now, attempts__lt=5).update(
        state="queued", available_at=now, error_code="worker_lease_lost"
    )
    SecurityJob.objects.filter(state="running", lease_until__lte=now, attempts__gte=5).update(
        state="failed", error_code="lease_exhausted"
    )
    from django.db.models import Q

    running = SecurityJob.objects.filter(state="running", purpose="render_report").values(
        "owner_id"
    )
    job = (
        SecurityJob.objects.select_for_update(skip_locked=True)
        .filter(state="queued", expires_at__gt=now, available_at__lte=now, attempts__lt=5)
        .exclude(Q(purpose="render_report") & Q(owner_id__in=running))
        .order_by("created_at")
        .first()
    )
    if not job:
        return None
    job.state, job.lease_id = "running", uuid.uuid4()
    job.lease_until = now + timedelta(seconds=300)
    job.heartbeat_at = now
    job.attempts += 1
    job.save()
    return job


def execute(job):
    stop = threading.Event()

    def heartbeat():
        try:
            while not stop.wait(30):
                changed = SecurityJob.objects.filter(
                    pk=job.pk,
                    state="running",
                    lease_id=job.lease_id,
                    lease_until__gt=timezone.now(),
                ).update(
                    heartbeat_at=timezone.now(), lease_until=timezone.now() + timedelta(seconds=300)
                )
                if not changed:
                    return
        finally:
            connections.close_all()

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        context = JobAuthorizationContext(job.actor_id, job.session_hash, job.grant_id)
        action = "download_report" if job.purpose == "render_report" else "read_original_document"
        if context.epoch() != job.permission_epoch:
            raise AccessDenied()
        source, metadata, authorize = select(context, job.input_record_id, action)
        payload = store.read(source, metadata.identity, authorize)
        result = invoke(job.purpose, payload, job.pk)
        if job.purpose == "render_report":
            if not result.startswith(b"%PDF-"):
                raise ValueError("parser_rejected_input")
        else:
            decoded = json.loads(result)
            if not isinstance(decoded, dict) or decoded.get("state") != "requires_review":
                raise ValueError("parser_rejected_input")
        if context.epoch() != job.permission_epoch:
            raise AccessDenied()
        output = SecureRecord(
            owner=job.owner,
            kind="report_snapshot" if job.purpose == "render_report" else "derived_snapshot",
            category=source.category,
            clinical_date=source.clinical_date,
            visibility=source.visibility,
            owner_only=source.owner_only if job.purpose == "render_report" else True,
            audience_grant=source.audience_grant if job.purpose == "render_report" else None,
            mime_type="application/pdf" if job.purpose == "render_report" else "application/json",
        )
        identity = Identity(output.owner_id, output.kind, output.object_id, output.pk, 1)

        def authorize_output(selected, operation):
            if (
                selected != identity
                or operation != "write"
                or context.epoch() != job.permission_epoch
            ):
                raise AccessDenied()
            select(context, source.pk, action)
            return True

        output.blob_name, output.ciphertext_sha256, output.ciphertext_bytes = store.write(
            result, identity, authorize_output
        )
        with transaction.atomic():
            current = SecurityJob.objects.select_for_update().get(pk=job.pk)
            if (
                current.state != "running"
                or current.lease_id != job.lease_id
                or current.lease_until <= timezone.now()
            ):
                return  # Leave expired ownership for the next bounded claim/recovery.
            if context.epoch() != job.permission_epoch:
                raise AccessDenied()
            select(context, source.pk, action)
            output.save()
            output.dependencies.add(source)
            current.output_record, current.state = output, "ready"
            current.save(update_fields=["output_record", "state"])
            if job.purpose == "parse_pdf":
                from labs.models import LabReport

                LabReport.objects.filter(
                    parser_job=job, state__in=["quarantined", "extracting"]
                ).update(state="needs_review")
            elif job.purpose == "parse_csv":
                from breathing.models import MeasurementImport

                MeasurementImport.objects.filter(parser_job=job, state="quarantined").update(
                    state="needs_review"
                )
    except KMSUnavailable:
        delay = [30, 120, 600, 3600][min(max(job.attempts - 1, 0), 3)]
        SecurityJob.objects.filter(
            pk=job.pk, lease_id=job.lease_id, state="running", lease_until__gt=timezone.now()
        ).update(
            state="queued" if job.attempts < 5 else "failed",
            available_at=timezone.now() + timedelta(seconds=delay),
            error_code="key_service_unavailable",
        )
    except AccessDenied:
        SecurityJob.objects.filter(pk=job.pk, lease_id=job.lease_id).update(
            state="cancelled", error_code="permission_changed"
        )
    except Exception:
        SecurityJob.objects.filter(pk=job.pk, lease_id=job.lease_id).update(
            state="failed", error_code="processing_failed"
        )
    finally:
        stop.set()
        thread.join(timeout=2)
