from datetime import timedelta
from pathlib import Path

from artifacts.models import DownloadTicket, SecureRecord, SecurityJob
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .models import AuditEvent, CacheEntry

MAINTENANCE_LOCK = 3103005


@transaction.atomic
def run(dry_run=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [MAINTENANCE_LOCK])
    now = timezone.now()
    if dry_run:
        from records.models import ActionReceipt, Mutation
        from reports.models import ExportBundle

        return {
            "dry_run": True,
            "due_ciphertext": SecureRecord.objects.filter(
                purge_after__lte=now, purged_at__isnull=True
            ).count(),
            "expired_exports": ExportBundle.objects.filter(expires_at__lte=now)
            .exclude(state="expired")
            .count(),
            "expired_receipts": ActionReceipt.objects.filter(
                created_at__lt=now - timedelta(days=30)
            ).count()
            + Mutation.objects.filter(created_at__lt=now - timedelta(days=30)).count(),
            "expired_audit_events": AuditEvent.objects.filter(
                created_at__lt=now - timedelta(days=365)
            ).count(),
        }
    expired = SecurityJob.objects.filter(expires_at__lte=now, output_record__isnull=False)
    SecureRecord.objects.filter(
        pk__in=expired.values("output_record_id"), deleted_at__isnull=True
    ).update(deleted_at=now, purge_after=now)
    from records.models import ActionReceipt, Mutation
    from reports.models import ExportBundle, ExportPart

    expired_bundles = ExportBundle.objects.filter(expires_at__lte=now)
    part_ids = ExportPart.objects.filter(bundle__in=expired_bundles).values("blob_id")
    SecureRecord.objects.filter(pk__in=part_ids, deleted_at__isnull=True).update(
        deleted_at=now, purge_after=now
    )
    SecureRecord.objects.filter(
        pk__in=expired_bundles.values("manifest_id"), deleted_at__isnull=True
    ).update(deleted_at=now, purge_after=now)
    expired_bundles.exclude(state="revoked").update(state="expired")
    for model in (ActionReceipt, Mutation):
        identifiers = list(
            model.objects.filter(created_at__lt=now - timedelta(days=30)).values_list(
                "pk", flat=True
            )[:1000]
        )
        model.objects.filter(pk__in=identifiers).delete()
    # Retain unresolved transport evidence. Only independently persisted accepted
    # revisions make an old batch eligible for raw-envelope expiry.
    from django.db.models import Count, F
    from ingest.models import IngestBatch, ItemReceipt

    candidates = (
        IngestBatch.objects.filter(state="processed", received_at__lt=now - timedelta(days=30))
        .annotate(receipt_count=Count("receipts"))
        .filter(receipt_count=F("item_count"))
        .exclude(receipts__revision_id__isnull=True)
    )
    SecureRecord.objects.filter(
        pk__in=candidates.values("evidence_id"), deleted_at__isnull=True
    ).update(deleted_at=now, purge_after=now)
    details = list(
        ItemReceipt.objects.filter(
            batch__in=candidates, batch__received_at__lt=now - timedelta(days=90)
        ).values_list("pk", flat=True)[:1000]
    )
    ItemReceipt.objects.filter(pk__in=details).delete()
    count = 0
    for record in SecureRecord.objects.select_for_update(skip_locked=True).filter(
        purge_after__lte=now, purged_at__isnull=True
    )[:1000]:
        path = Path(settings.HEALTH03_BLOB_ROOT) / record.blob_name
        if path.parent != Path(settings.HEALTH03_BLOB_ROOT):
            raise ValueError("Invalid blob reference")
        path.unlink(missing_ok=True)
        record.purged_at = now
        record.save(update_fields=["purged_at"])
        count += 1
    DownloadTicket.objects.filter(deadline__lt=now).delete()
    CacheEntry.objects.filter(expires_at__lt=now).delete()
    AuditEvent.objects.filter(created_at__lt=now - timedelta(days=365)).delete()
    root = Path(settings.HEALTH03_BLOB_ROOT)
    if root.exists():
        for path in root.iterdir():
            if path.is_file() and path.stat().st_mtime < (now - timedelta(hours=24)).timestamp():
                if not SecureRecord.objects.filter(
                    blob_name=path.name, purged_at__isnull=True
                ).exists():
                    path.unlink()
    from .models import DeletionRequest

    for deletion in DeletionRequest.objects.filter(purged_at=None)[:100]:
        if not SecureRecord.objects.filter(owner_id=deletion.owner_id, purged_at=None).exists():
            deletion.purged_at = now
            deletion.save(update_fields=["purged_at"])
    return {"purged_records": count}
