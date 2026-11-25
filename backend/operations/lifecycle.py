import uuid
from datetime import timedelta

from access.models import SharingGrant
from access.policy import AccessDenied, AuthorizationContext
from accounts.models import Account, Invitation, SessionSecurity
from accounts.policy import fresh, session_state
from artifacts.models import DownloadTicket, SecureRecord, SecurityJob
from artifacts.selectors import select
from django.conf import settings
from django.contrib.auth import logout
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from uploader.models import DeviceRegistration
from uploader.policy import revoke_account_families

from . import audit, ledger
from .models import OperationalControl


@transaction.atomic
def reduce_record(request, record_id, delete=False):
    context = AuthorizationContext(request)
    record, metadata, _ = select(context, record_id, "write")
    now = timezone.now()
    if delete:
        record.deleted_at, record.purge_after = now, now + timedelta(hours=24)
        record.save(update_fields=["deleted_at", "purge_after"])
        from labs.models import LabReport, PublishedResult
        from records.models import Record

        ids = {record.pk}
        if record.kind == "lab_document":
            reports = LabReport.objects.filter(original=record)
            related = Record.objects.filter(
                pk__in=PublishedResult.objects.filter(report__in=reports).values("record_id")
            )
            related.update(deleted_at=now)
            ids.update(
                SecureRecord.objects.filter(object_id__in=related.values("pk")).values_list(
                    "pk", flat=True
                )
            )
            ids.update(
                SecureRecord.objects.filter(
                    object_id__in=reports.exclude(review=None).values("review_id")
                ).values_list("pk", flat=True)
            )
        frontier = ids.copy()
        while frontier:
            frontier = (
                set(
                    SecureRecord.objects.filter(dependencies__pk__in=frontier).values_list(
                        "pk", flat=True
                    )
                )
                - ids
            )
            ids.update(frontier)
        SecureRecord.objects.filter(pk__in=ids).update(
            deleted_at=now, purge_after=now + timedelta(hours=24)
        )
        action = "record_deleted"
    else:
        record.visibility = "private"
        record.save(update_fields=["visibility"])
        action = "record_private"
    Account.objects.filter(pk=record.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
    SecurityJob.objects.filter(owner_id=record.owner_id, grant_id__isnull=False).exclude(
        state__in=["failed", "cancelled"]
    ).update(state="cancelled", error_code="permission_changed")
    DownloadTicket.objects.filter(record__owner_id=record.owner_id).delete()
    ledger.enqueue(record.owner_id, action, record.object_id)
    audit.emit(action, request.user, record.object_id)
    return {
        "accepted_at": now.isoformat(),
        "purge_by": record.purge_after.isoformat() if delete else None,
        "durability": "pending",
        "context_reset_required": True,
        "next_permission_epoch": context.epoch(),
    }


@transaction.atomic
def close_account(request):
    state = session_state(request)
    if not fresh(state) or request.user.role != "owner":
        raise AccessDenied()
    owner, now = request.user, timezone.now()
    Account.objects.filter(pk=owner.pk).update(
        is_active=False, security_epoch=uuid.uuid4(), sharing_epoch=F("sharing_epoch") + 1
    )
    SessionSecurity.objects.filter(account=owner).delete()
    revoke_account_families(owner)
    DeviceRegistration.objects.filter(owner=owner).update(revoked_at=now)
    from ingest.models import SourceConnection
    from reports.models import ExportBundle

    SourceConnection.objects.filter(device__owner=owner).update(disabled_at=now)
    ExportBundle.objects.filter(owner=owner).update(state="revoked", error_code="account_closed")
    SharingGrant.objects.filter(owner=owner).update(state="revoked", revoked_at=now)
    Invitation.objects.filter(account=owner).delete()
    DownloadTicket.objects.filter(record__owner=owner).delete()
    SecurityJob.objects.filter(owner=owner).update(state="cancelled", error_code="account_closed")
    SecureRecord.objects.filter(owner=owner, deleted_at__isnull=True).update(
        deleted_at=now, purge_after=now + timedelta(hours=24)
    )
    ledger.enqueue(owner.pk, "account_closed", owner.pk)
    audit.emit("account_closed", owner, owner.pk, outcome="pending")
    logout(request)
    request.account_closure_accepted = True
    return {
        "accepted_at": now.isoformat(),
        "purge_by": (now + timedelta(hours=24)).isoformat(),
        "backup_retention_days": backup_retention_days(),
        "durability": "pending" if settings.HEALTH03_BACKUPS_ENABLED else "local_only",
    }


@transaction.atomic
def incident_lock():
    OperationalControl.objects.update_or_create(pk=1, defaults={"incident_locked": True})
    SessionSecurity.objects.all().delete()
    DownloadTicket.objects.all().delete()
    for account in Account.objects.all():
        revoke_account_families(account)
        Account.objects.filter(pk=account.pk).update(security_epoch=uuid.uuid4())
    SecurityJob.objects.exclude(state="failed").update(
        state="cancelled", error_code="incident_lock"
    )
    from artifacts import store

    if hasattr(store, "_service"):
        store._service.lock()
    audit.emit("incident_lock")


def backup_retention_days():
    from .models import BackupSet

    return (
        35
        if settings.HEALTH03_BACKUPS_ENABLED or BackupSet.objects.filter(state="complete").exists()
        else 0
    )
