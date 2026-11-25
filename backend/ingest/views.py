import hashlib
import uuid
from contextlib import contextmanager
from pathlib import Path

import rfc8785
from access.policy import AccessDenied
from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity, TransitKMS
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from jobs.service import enqueue
from records.http import endpoint
from records.service import owner_context
from records.validation import DomainError, parse_json
from uploader.backend import UploaderCore, has_machine_credentials
from uploader.models import DeviceRegistration

from .models import IngestBatch, SourceConnection, SyncRequest


def device(request, scope):
    if not has_machine_credentials(request):
        raise DomainError("uploader_credentials_required", 401)
    valid, oauth = UploaderCore().verify_request(request, scopes=[scope])
    if not valid:
        raise DomainError("uploader_credentials_required", 401)
    return oauth.health03_device


@contextmanager
def intake_transaction(evidence):
    # Own the outer commit so a failed enqueue/commit also rolls back the file.
    try:
        with transaction.atomic(durable=True):
            yield
    except Exception:
        if evidence.blob_name:
            # A lost commit acknowledgement is ambiguous. Retain the file if the
            # database is unavailable. The retention worker reconciles it later.
            if not SecureRecord.objects.filter(pk=evidence.pk, blob_name=evidence.blob_name).exists():
                (Path(settings.HEALTH03_BLOB_ROOT) / evidence.blob_name).unlink(missing_ok=True)
        raise


@csrf_exempt
@endpoint({"POST", "GET"})
def batches(request, batch_id=None):
    registered = device(request, "ingest:status" if request.method == "GET" else "ingest:write")
    if request.method == "GET":
        batch = IngestBatch.objects.filter(pk=batch_id, source__device=registered).first()
        if not batch:
            raise AccessDenied()
        return {
            "batch_id": str(batch.pk),
            "state": batch.state,
            "items": list(
                batch.receipts.order_by("ordinal").values(
                    "ordinal", "outcome", "reason", "record_id", "revision_id", "disposition"
                )
            ),
            "durably_retained": True,
            "clinical_acceptance": batch.receipts.filter(outcome="accepted", disposition="clinical").exists(),
        }
    body = parse_json(request.body)
    if (
        set(body)
        != {
            "schema_version",
            "canonicalization",
            "batch_id",
            "source_namespace",
            "generated_at",
            "items",
        }
        or body["schema_version"] != "pb-health-export-1"
        or body["canonicalization"] != "jcs-rfc8785-v1"
    ):
        raise DomainError("unsupported_batch_schema", 400)
    if not isinstance(body["items"], list) or not 1 <= len(body["items"]) <= 1000:
        raise DomainError("invalid_batch_size")
    try:
        identifier, namespace = uuid.UUID(body["batch_id"]), uuid.UUID(body["source_namespace"])
    except (ValueError, TypeError):
        raise DomainError("invalid_batch_identity", 400) from None
    from datetime import datetime

    generated = datetime.fromisoformat(body["generated_at"])
    if generated.tzinfo is None:
        raise DomainError("invalid_generated_at")
    try:
        canonical = rfc8785.dumps(body)
    except (ValueError, TypeError):
        raise DomainError("invalid_canonical_payload", 400) from None
    digest = TransitKMS().identity_digest(
        registered.owner_id, "batch", hashlib.sha256(canonical).hexdigest(), str(namespace), 1
    )
    previous = IngestBatch.objects.filter(pk=identifier).first()
    if previous:
        if previous.source.device_id != registered.pk or previous.body_digest != digest:
            raise DomainError("batch_conflict", 409)
        return {
            "batch_id": str(previous.pk),
            "state": previous.state,
            "receipt_url": f"/api/v1/ingestion/batches/{previous.pk}",
        }
    evidence = SecureRecord(
        owner_id=registered.owner_id,
        kind="source_identity",
        category="sleep_activity",
        clinical_date=None,
    )
    identity = Identity(registered.owner_id, evidence.kind, evidence.object_id, evidence.pk, 1)

    def authorize(selected, operation):
        device(request, "ingest:write")
        return selected == identity and operation == "write"

    with intake_transaction(evidence):
        current = DeviceRegistration.objects.select_for_update().get(pk=registered.pk)
        device(request, "ingest:write")
        source, _ = SourceConnection.objects.get_or_create(
            namespace=namespace, defaults={"device": current}
        )
        if source.device_id != registered.pk or source.disabled_at:
            raise AccessDenied()
        existing = IngestBatch.objects.filter(pk=identifier).first()
        if existing:
            if existing.source_id != source.pk or existing.body_digest != digest:
                raise DomainError("batch_conflict", 409)
            return {
                "batch_id": str(existing.pk),
                "state": existing.state,
                "receipt_url": f"/api/v1/ingestion/batches/{existing.pk}",
            }
        evidence.blob_name, evidence.ciphertext_sha256, evidence.ciphertext_bytes = store.write(
            canonical, identity, authorize
        )
        evidence.save()
        # A different device can independently choose this UUID while our device is locked.
        _, created = IngestBatch.objects.get_or_create(
            id=identifier,
            defaults={
                "source": source, "body_digest": digest, "evidence": evidence,
                "item_count": len(body["items"]),
            },
        )
        if not created:
            raise DomainError("batch_conflict", 409)
        enqueue("ingest", identifier, 1)
    return JsonResponse(
        {
            "batch_id": str(identifier),
            "state": "received",
            "receipt_url": f"/api/v1/ingestion/batches/{identifier}",
        },
        status=202,
    )


@endpoint({"GET", "POST"})
def sync(request):
    _, patient = owner_context(request)
    if request.method == "POST":
        body = parse_json(request.body)
        registered = DeviceRegistration.objects.filter(
            pk=body.get("device_id"), owner_id=patient.owner_id, revoked_at__isnull=True
        ).first()
        if not registered:
            raise DomainError("device_unavailable", 409)
        from records.actions import Command

        receipt = Command(request)

        def commit():
            DeviceRegistration.objects.select_for_update().get(pk=registered.pk)
            if DeviceRegistration.objects.filter(
                pk=registered.pk, revoked_at__isnull=False
            ).exists():
                raise DomainError("device_unavailable", 409)
            pending = SyncRequest.objects.filter(
                device=registered, state__in=["queued", "requesting", "syncing"]
            ).first()
            command = pending or SyncRequest.objects.create(device=registered)
            return {"id": str(command.pk), "state": command.state}

        return receipt.run(commit)
    return {
        "requests": list(
            SyncRequest.objects.filter(device__owner_id=patient.owner_id)
            .order_by("-requested_at")
            .values("id", "state", "requested_at", "updated_at")[:50]
        )
    }


@csrf_exempt
@endpoint({"POST"})
def assets(request):
    registered = device(request, "ingest:write")
    try:
        namespace = uuid.UUID(request.headers["X-Source-Namespace"])
        source_id = request.headers["X-Source-Record-ID"]
        if not 1 <= len(source_id) <= 200 or any(ord(char) < 32 for char in source_id):
            raise ValueError
        kind = request.headers["X-Source-Kind"]
    except (KeyError, ValueError):
        raise DomainError("asset_identity_required", 400) from None
    if len(request.body) > 25 * 1024 * 1024:
        raise DomainError("asset_too_large", 413)
    from .canonical import authorizer
    from .models import SourceAsset

    source = SourceConnection.objects.filter(
        namespace=namespace, device=registered, disabled_at__isnull=True
    ).first()
    if not source:
        raise AccessDenied()
    kms = TransitKMS()
    intent = kms.identity_digest(registered.owner_id, kind, source_id, str(namespace), 1)
    digest = kms.identity_digest(
        registered.owner_id, "asset", hashlib.sha256(request.body).hexdigest(), str(namespace), 1
    )
    prior = SourceAsset.objects.filter(
        source=source, intent_digest=intent, content_digest=digest
    ).first()
    if prior:
        return {"id": str(prior.pk), "state": "ready"}
    blob = SecureRecord(
        owner_id=registered.owner_id,
        kind="source_identity",
        category="sleep_activity",
        clinical_date=None,
        owner_only=True,
    )
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
    with intake_transaction(blob):
        DeviceRegistration.objects.select_for_update().get(pk=registered.pk)
        device(request, "ingest:write")
        prior = SourceAsset.objects.filter(
            source=source, intent_digest=intent, content_digest=digest
        ).first()
        if prior:
            return {"id": str(prior.pk), "state": "ready"}
        blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
            request.body, identity, authorizer(source, identity)
        )
        blob.save()
        asset = SourceAsset.objects.create(
            source=source, intent_digest=intent, content_digest=digest, evidence=blob
        )
    return {"id": str(asset.pk), "state": "ready"}


@csrf_exempt
@endpoint({"POST"})
def acknowledge(request, command_id):
    registered = device(request, "ingest:status")
    body = parse_json(request.body)
    target = body.get("state")
    allowed = {
        "queued": {"requesting", "syncing", "device_unavailable", "failed"},
        "requesting": {"syncing", "device_unavailable", "failed"},
        "syncing": {"completed", "failed"},
        "completed": set(),
        "failed": set(),
        "device_unavailable": set(),
    }
    with transaction.atomic():
        command = (
            SyncRequest.objects.select_for_update().filter(pk=command_id, device=registered).first()
        )
        if not command:
            raise AccessDenied()
        if target != command.state and target not in allowed[command.state]:
            raise DomainError("invalid_sync_transition", 409)
        command.state = target
        command.save()
    return {"id": str(command.pk), "state": command.state}
