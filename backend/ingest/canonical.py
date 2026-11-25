"""Immutable source-version commits; intake credentials never expose clinical reads."""

import hashlib
import json
from datetime import timedelta

import rfc8785
from accounts.policy import eligible
from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity, TransitKMS
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from jobs.models import Job
from records.models import Patient, Record, Revision
from records.validation import DomainError

from . import lookups
from .models import SourceAsset, SourceIdentity, SourceTombstone, SourceVersion


def source_active(source):
    source.refresh_from_db()
    device = source.device
    device.refresh_from_db()
    return not source.disabled_at and not device.revoked_at and eligible(device.owner)


def authorizer(source, identity):
    def authorize(selected, action):
        if selected != identity or action not in {"read", "write"} or not source_active(source):
            raise DomainError("source_revoked", 403)
        return True

    return authorize


def enabled_kinds():
    from .mapping import SUPPORTED_KINDS

    return set(SUPPORTED_KINDS)


def qualified(item):
    from .mapping import normalize

    mapped, category, day, _ = normalize(item)
    return mapped, category, day


def commit_item(source, item, job):
    if not isinstance(item, dict) or set(item) != {
        "source_record_id",
        "source_revision",
        "kind",
        "operation",
        "payload",
    }:
        raise DomainError("invalid_item_schema")
    source_id = item["source_record_id"]
    if (
        not isinstance(source_id, str)
        or not 1 <= len(source_id) <= 200
        or any(ord(char) < 32 for char in source_id)
    ):
        raise DomainError("invalid_source_identity")
    number = item["source_revision"]
    if type(number) is not int or not 1 <= number <= 9007199254740991:
        raise DomainError("invalid_source_revision")
    if item["operation"] not in {"upsert", "tombstone"}:
        raise DomainError("invalid_source_operation")
    kms = TransitKMS()
    owner = source.device.owner
    lookup_digests = lookups.digests(kms, source, item["kind"], source_id)
    digest = lookup_digests[1]
    body_digest = kms.identity_digest(
        owner.pk,
        "source-payload",
        hashlib.sha256(rfc8785.dumps(item)).hexdigest(),
        str(source.namespace),
        1,
    )
    if SourceTombstone.objects.filter(source=source, identity_digest=digest).exists():
        return "blocked_deleted", None, None
    existing = lookups.resolve(source, item["kind"], lookup_digests)
    if existing:
        previous = SourceVersion.objects.filter(identity=existing, source_revision=number).first()
        if previous:
            if previous.payload_digest != body_digest:
                return "conflict", None, None
            return "duplicate", existing.record_id, previous.revision_id
    if item["operation"] == "upsert":
        from .evidence import native_extension
        from .mapping import normalize
        from .phone_wire import compact_assets

        expanded = native_extension(source, item, digest)
        mapped, category, day, payload = normalize({**item, "payload": expanded})
        payload = compact_assets(payload)
    else:
        mapped, category, day = "observation", "sleep_activity", None
    patient, _ = Patient.objects.get_or_create(owner=owner)
    record = existing.record if existing else Record(patient=patient, kind=mapped)
    blob = None
    if item["operation"] == "upsert":
        from .evidence import asset_ids

        attached_assets = asset_ids(payload)
        for asset_id in attached_assets:
            if not SourceAsset.objects.filter(
                pk=asset_id, source=source, intent_digest=digest, evidence__deleted_at__isnull=True
            ).exists():
                raise DomainError("asset_not_ready", 503)
        blob = SecureRecord(
            owner=owner,
            object_id=record.pk,
            kind="clinical_record",
            category=category,
            clinical_date=day,
            owner_only=mapped in {"body_context", "source_record"}
            or payload.get("clinical_eligible") is False,
        )
        identity = Identity(owner.pk, blob.kind, record.pk, blob.pk, 1)
        evidence = {
            **payload,
            "source_revision": number,
            "source_identity": source_id,
            "source_namespace": str(source.namespace),
            "source_kind": item["kind"],
        }
        blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
            json.dumps(evidence, separators=(",", ":")).encode(),
            identity,
            authorizer(source, identity),
        )
    with transaction.atomic():
        Patient.objects.select_for_update().get(pk=patient.pk)
        lease = Job.objects.select_for_update().get(pk=job.pk)
        if (
            lease.state != "running"
            or lease.lease_token != job.lease_token
            or lease.lease_until <= timezone.now()
        ):
            raise DomainError("lease_lost", 503)
        if not source_active(source):
            raise DomainError("source_revoked", 403)
        if SourceTombstone.objects.filter(source=source, identity_digest=digest).exists():
            return "blocked_deleted", None, None
        current = lookups.resolve(source, item["kind"], lookup_digests)
        if current and current.record_id != record.pk:
            raise DomainError("identity_race", 503)
        if current:
            previous = SourceVersion.objects.filter(
                identity=current, source_revision=number
            ).first()
            if previous:
                return (
                    ("duplicate" if previous.payload_digest == body_digest else "conflict"),
                    current.record_id,
                    previous.revision_id,
                )
            record = Record.objects.select_for_update().get(pk=current.record_id)
        else:
            record.save()
            current = SourceIdentity.objects.create(
                source=source, kind=item["kind"], digest=digest, record=record
            )
        lookups.index(current, lookup_digests)
        if record.deleted_at:
            return "blocked_deleted", None, None
        if item["operation"] == "tombstone":
            if number <= current.highest_revision:
                return "superseded", record.pk, None
            now = timezone.now()
            record.deleted_at = now
            record.save(update_fields=["deleted_at"])
            SourceTombstone.objects.get_or_create(source=source, identity_digest=digest)
            ids = set(SecureRecord.objects.filter(object_id=record.pk).values_list("pk", flat=True))
            frontier = ids.copy()
            while frontier:
                children = (
                    set(
                        SecureRecord.objects.filter(
                            Q(dependencies__pk__in=frontier) | Q(parent_id__in=frontier)
                        ).values_list("pk", flat=True)
                    )
                    - ids
                )
                ids.update(children)
                frontier = children
            SecureRecord.objects.filter(pk__in=ids).update(
                deleted_at=now, purge_after=now + timedelta(hours=24)
            )
            from accounts.models import Account
            from artifacts.models import DownloadTicket, SecurityJob
            from records.models import Designation

            Account.objects.filter(pk=owner.pk).update(sharing_epoch=F("sharing_epoch") + 1)
            Designation.objects.filter(record=record).update(record=None, version=F("version") + 1)
            DownloadTicket.objects.filter(record__owner=owner).delete()
            SecurityJob.objects.filter(owner=owner, grant_id__isnull=False).update(
                state="cancelled", error_code="permission_changed"
            )
            from operations.ledger import enqueue

            enqueue(owner.pk, "record_deleted", record.pk)
            revision = None
            outcome = "accepted"
        else:
            blob.save()
            SecureRecord.objects.filter(sourceasset__pk__in=attached_assets).update(parent=blob)
            record.version += 1
            revision = Revision.objects.create(
                record=record,
                version=record.version,
                blob=blob,
                measured_start=__import__("datetime").datetime.fromisoformat(
                    payload["measured_start"]
                )
                if payload.get("measured_start")
                else None,
            )
            outcome = "accepted" if number > current.highest_revision else "superseded"
            if outcome == "accepted":
                record.current = revision
                record.kind = mapped
            record.save(update_fields=["current", "version", "kind"])
            if outcome == "accepted":
                from .mapping import select_imported

                select_imported(record, revision, payload, day)
        SourceVersion.objects.create(
            identity=current,
            source_revision=number,
            payload_digest=body_digest,
            revision=revision,
            outcome=outcome,
            disposition=payload["record_status"] if item["operation"] == "upsert" else "deleted",
        )
        if number > current.highest_revision:
            current.highest_revision = number
            current.save(update_fields=["highest_revision"])
            Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
            from jobs.service import enqueue

            if record.kind in {"weight", "pulmonary"}:
                enqueue("invalidate", record.pk, record.version)
        return outcome, record.pk, revision.pk if revision else None
