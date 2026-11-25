"""Owner-only access to received source evidence; never exposed through phone upload ingress."""

from access.policy import AccessDenied
from artifacts import store
from artifacts.selectors import select
from django.http import HttpResponse
from records import service
from records.http import endpoint
from records.validation import DomainError

from .models import SourceAsset, SourceIdentity


def asset_ids(payload):
    result = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "asset_ids":
                    result.update(child)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    if len(result) > 100:
        raise DomainError("too_many_asset_links")
    return result


@endpoint({"GET"})
def records(request):
    service.owner_context(request)
    kinds = {
        "body": ["weight", "body_observation", "body_context"],
        "breathing": ["pulmonary"],
        "blood_pressure": ["blood_pressure"],
        "sleep": ["sleep", "workout", "observation", "source_record"],
    }.get(
        request.GET.get("domain"),
        [
            "weight",
            "body_observation",
            "body_context",
            "pulmonary",
            "sleep",
            "workout",
            "observation",
            "blood_pressure",
            "source_record",
        ],
    )
    return service.permitted(
        request,
        kinds,
        request.GET.get("from"),
        request.GET.get("to"),
        50,
        request.GET.get("cursor"),
        phone_only=True,
    )


@endpoint({"GET"})
def asset(request, record_id, asset_id):
    context, patient = service.owner_context(request)
    identity = (
        SourceIdentity.objects.select_related("record__current")
        .filter(record_id=record_id, record__patient=patient, record__deleted_at__isnull=True)
        .first()
    )
    if identity is None:
        raise AccessDenied()
    value = service.dto(context, identity.record)
    if str(asset_id) not in asset_ids(value["data"]):
        raise AccessDenied()
    row = SourceAsset.objects.filter(pk=asset_id, source=identity.source).first()
    if row is None:
        raise AccessDenied()
    blob, metadata, authorize = select(context, row.evidence_id)
    raw = store.read(blob, metadata.identity, authorize)
    response = HttpResponse(raw, content_type="application/octet-stream")
    response["Content-Disposition"] = 'attachment; filename="phone-evidence.bin"'
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def native_extension(source, item, intent_digest):
    """Read the phone's ordered, hashed JSON chunks without changing the source identity."""
    import hashlib
    import json

    from crypto.envelopes import Identity

    from .canonical import authorizer

    payload = item["payload"]
    descriptor = payload.get("native_record_assets")
    if not descriptor or "native_record" in payload:
        return payload
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("encoding") != "concatenated-utf8-json-v1"
    ):
        raise DomainError("invalid_native_record_assets")
    ids = descriptor.get("ids")
    size = descriptor.get("bytes")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or type(size) is not int or size < 0:
        raise DomainError("invalid_native_record_assets")
    if not set(ids) <= set(payload.get("asset_ids", [])):
        raise DomainError("native_asset_not_attached")
    # Larger originals remain intact and downloadable even when not expanded into inline records.
    if size > 100 * 1024 * 1024:
        return {**payload, "native_expansion": "download_only_size_limit"}
    chunks = bytearray()
    for asset_id in ids:
        row = (
            SourceAsset.objects.select_related("evidence")
            .filter(
                pk=asset_id,
                source=source,
                intent_digest=intent_digest,
                evidence__deleted_at__isnull=True,
            )
            .first()
        )
        if row is None:
            raise DomainError("asset_not_ready", 503)
        blob = row.evidence
        identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
        chunk = store.read(blob, identity, authorizer(source, identity))
        if len(chunks) + len(chunk) > size:
            raise DomainError("native_evidence_size_mismatch")
        chunks.extend(chunk)
    if len(chunks) != size or hashlib.sha256(chunks).hexdigest() != descriptor.get("sha256"):
        raise DomainError("native_evidence_digest_mismatch")
    try:
        native = json.loads(chunks)
    except (ValueError, UnicodeError):
        raise DomainError("invalid_native_evidence_json") from None
    if not isinstance(native, dict):
        raise DomainError("invalid_native_evidence_json")
    return {**payload, "native_record": native, "native_expansion": "verified_asset_chunks"}
