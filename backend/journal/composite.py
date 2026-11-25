from datetime import timedelta

from access.policy import AccessDenied
from accounts.models import Account
from artifacts.models import DownloadTicket, SecureRecord, SecurityJob
from django.db.models import F
from django.utils import timezone
from operations import ledger
from records import service
from records.components import prepare
from records.models import Record
from records.validation import DomainError

from .models import MedicationLink
from .service import validate


def prepare_composite(request, body, record_id):
    context, patient = service.owner_context(request)
    operations = body.get("linked_medication_operations", [])
    expected = body.get("expected_link_revisions", {})
    included = body.get("included_medication_ids", [])
    if (
        not isinstance(operations, list)
        or len(operations) > 50
        or not isinstance(expected, dict)
        or not isinstance(included, list)
        or len(included) > 100
    ):
        raise DomainError("invalid_composite")
    payload = {
        **body["entry"],
        "visibility": body.get("visibility", "private"),
        "included_medication_ids": included,
    }
    payload, day, visibility = validate("journal", payload)
    prepared = []
    deleted = []
    new_ids = {}
    touched = set()
    for operation in operations:
        action = operation.get("action")
        identifier = operation.get("id")
        if identifier and identifier in touched:
            raise DomainError("duplicate_medication_operation")
        if identifier:
            touched.add(identifier)
        if action == "delete":
            event = Record.objects.filter(
                pk=identifier, patient=patient, kind="medication", deleted_at__isnull=True
            ).first()
            if not event:
                raise AccessDenied()
            if operation.get("etag") != service.etag(event):
                raise DomainError("revision_conflict", 412)
            deleted.append((event.pk, event.version))
            continue
        if action not in {"create", "update"}:
            raise DomainError("invalid_medication_operation")
        if action == "update" and not identifier:
            raise DomainError("medication_id_required")
        data, med_day, med_visibility = validate(
            "medication", {**operation["data"], "visibility": "private"}
        )
        event_id, save = prepare(
            context,
            patient,
            "medication",
            data,
            med_day,
            record_id=identifier,
            expected_etag=operation.get("etag"),
        )
        prepared.append((event_id, save))
        if operation.get("client_id"):
            new_ids[operation["client_id"]] = str(event_id)
    included = [new_ids.get(value, value) for value in included]
    payload["included_medication_ids"] = included
    prepared_ids = {str(identifier) for identifier, _ in prepared}
    if len(set(included)) != len(included):
        raise DomainError("duplicate_medication_selection")
    for identifier in included:
        if identifier in prepared_ids:
            continue
        event = Record.objects.filter(
            pk=identifier, patient=patient, kind="medication", deleted_at__isnull=True
        ).first()
        if not event:
            raise AccessDenied()
        if expected.get(identifier) != service.etag(event):
            raise DomainError("linked_revision_required", 412)
    if any(str(identifier) in included for identifier, _ in deleted):
        raise DomainError("deleted_medication_selected")

    def commit(record, revision, patient):
        for identifier, tag in expected.items():
            current = (
                Record.objects.select_for_update()
                .filter(pk=identifier, patient=patient, deleted_at__isnull=True)
                .first()
            )
            if not current or service.etag(current) != tag:
                raise DomainError("revision_conflict", 412)
        for _, save in prepared:
            save()
        for identifier, version in deleted:
            current = Record.objects.select_for_update().get(pk=identifier)
            if current.deleted_at or current.version != version:
                raise DomainError("revision_conflict", 412)
            now = timezone.now()
            current.deleted_at = now
            current.save(update_fields=["deleted_at"])
            SecureRecord.objects.filter(object_id=identifier).update(
                deleted_at=now, purge_after=now + timedelta(hours=24)
            )
            MedicationLink.objects.filter(event=current).delete()
            ledger.enqueue(patient.owner_id, "record_deleted", identifier)
        old = set(MedicationLink.objects.filter(entry=record).values_list("event_id", flat=True))
        MedicationLink.objects.filter(entry=record).exclude(event_id__in=included).delete()
        for identifier in included:
            event = Record.objects.select_for_update().get(
                pk=identifier, patient=patient, kind="medication", deleted_at__isnull=True
            )
            MedicationLink.objects.get_or_create(entry=record, event=event)
            event.current.blob.visibility = (
                "shared" if visibility == "shared" else event.current.blob.visibility
            )
            event.current.blob.save(update_fields=["visibility"])
        for identifier in old - {__import__("uuid").UUID(value) for value in included}:
            if not MedicationLink.objects.filter(
                event_id=identifier,
                entry__deleted_at__isnull=True,
                entry__current__blob__visibility="shared",
            ).exists():
                SecureRecord.objects.filter(object_id=identifier).update(visibility="private")
                ledger.enqueue(patient.owner_id, "record_private", identifier)
        # Link changes invalidate clinician jobs/tickets immediately, independently of payload caches.
        if old or included or deleted:
            Account.objects.filter(pk=patient.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
            DownloadTicket.objects.filter(record__owner_id=patient.owner_id).delete()
            SecurityJob.objects.filter(owner_id=patient.owner_id, grant_id__isnull=False).update(
                state="cancelled", error_code="permission_changed"
            )

    return payload, day, visibility, commit
