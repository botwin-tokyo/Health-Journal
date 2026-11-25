from access.policy import AccessDenied
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from records.http import endpoint

from .lifecycle import close_account, reduce_record


@require_POST
def delete_account(request):
    try:
        return JsonResponse(close_account(request), status=202)
    except AccessDenied:
        return JsonResponse({"code": "reauthentication_required"}, status=403)


@endpoint({"POST"})
def delete_record(request, record_id):
    from django.db.models import Q
    from records import service
    from records.models import Record

    _, patient = service.owner_context(request)
    record = Record.objects.filter(
        Q(pk=record_id) | Q(current__blob_id=record_id), patient=patient
    ).first()
    if record:
        return service.delete(request, record.pk)
    return reduce_record(request, record_id, delete=True)


@endpoint({"POST", "GET"})
def deletion_requests(request, request_id=None):
    from datetime import timedelta

    from accounts.policy import fresh, session_state
    from django.db import transaction
    from django.utils import timezone
    from records.service import owner_context
    from records.validation import DomainError, parse_json

    from .models import DeletionRequest, SecurityOutbox

    _, patient = owner_context(request)
    if request.method == "GET":
        row = DeletionRequest.objects.filter(pk=request_id, owner_id=patient.owner_id).first()
        if row is None:
            raise AccessDenied()
        return {
            "id": str(row.pk),
            "purge_by": row.purge_by,
            "purged_at": row.purged_at,
            "backup_retention_days": row.backup_retention_days,
            "durability": "local_only"
            if not settings.HEALTH03_BACKUPS_ENABLED
            else "pending"
            if SecurityOutbox.objects.filter(owner_id=row.owner_id, acknowledged_at=None).exists()
            else "acknowledged",
        }
    if not fresh(session_state(request)):
        raise DomainError("reauthentication_required", 403)
    body = parse_json(request.body)
    if body.get("scope") != "account" or body.get("confirm") is not True:
        raise DomainError("explicit_account_deletion_required")
    with transaction.atomic():
        from .lifecycle import backup_retention_days

        row = DeletionRequest.objects.create(
            owner_id=patient.owner_id,
            purge_by=timezone.now() + timedelta(hours=24),
            backup_retention_days=backup_retention_days(),
        )
        receipt = close_account(request)
    return {**receipt, "id": str(row.pk), "status_access": "operator_support_only_after_logout"}


@endpoint({"GET"})
def ready(request):
    from crypto.envelopes import TransitKMS
    from django.db import connection
    from records.service import owner_context

    from .models import OperationalControl

    owner_context(request)
    if OperationalControl.objects.filter(incident_locked=True).exists():
        return JsonResponse({"ready": False}, status=503)
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    TransitKMS().identity_digest(request.user.pk, "readiness", "public-canary", "internal", 1)
    return {"ready": True}
