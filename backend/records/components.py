"""Prepare encrypted composite revisions before entering the final transaction."""

import json

from access.policy import AccessDenied, RecordRef
from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity

from .models import Record, Revision
from .service import KINDS, etag
from .validation import DomainError


def prepare(
    context, patient, kind, payload, day, visibility="private", record_id=None, expected_etag=None
):
    record = (
        Record.objects.filter(
            pk=record_id, patient=patient, kind=kind, deleted_at__isnull=True
        ).first()
        if record_id
        else Record(patient=patient, kind=kind)
    )
    if not record:
        raise AccessDenied()
    version = record.version
    if record_id and expected_etag != etag(record):
        raise DomainError("revision_conflict", 412)
    envelope_kind, category = KINDS[kind]
    blob = SecureRecord(
        owner_id=patient.owner_id,
        object_id=record.pk,
        kind=envelope_kind,
        category=category,
        clinical_date=day,
        visibility=visibility,
    )
    identity = Identity(patient.owner_id, envelope_kind, record.pk, blob.pk, 1)
    ref = RecordRef(identity, category, day, visibility)
    blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
        identity,
        context.envelope_authorizer(ref, "write"),
    )

    def commit(parent=None):
        context.require(ref, "write")
        if record_id:
            current = Record.objects.select_for_update().get(pk=record_id)
            if current.deleted_at or current.version != version:
                raise DomainError("revision_conflict", 412)
        else:
            current = record
            current.save()
        if parent:
            if parent.owner_id != patient.owner_id:
                raise AccessDenied()
            blob.parent = parent
        blob.save()
        revision = Revision.objects.create(
            record=current,
            version=version + 1,
            blob=blob,
            measured_start=payload.get("measured_start"),
        )
        current.current, current.version = revision, version + 1
        current.save(update_fields=["current", "version"])
        return current

    return record.pk, commit
