import hashlib
import json
import uuid
from datetime import timedelta

from access.policy import AccessDenied, AuthorizationContext, RecordRef
from accounts.models import Account
from artifacts import store
from artifacts.models import SecureRecord
from artifacts.selectors import select
from crypto.envelopes import Identity, TransitKMS
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.crypto import salted_hmac
from operations import audit, ledger

from .models import Mutation, Patient, Record, Revision
from .validation import DomainError

KINDS = {
    "weight": ("clinical_record", "body"),
    "pulmonary": ("clinical_record", "breathing"),
    "sleep": ("clinical_record", "sleep_activity"),
    "workout": ("clinical_record", "sleep_activity"),
    "observation": ("clinical_record", "sleep_activity"),
    "blood_pressure": ("clinical_record", "sleep_activity"),
    "journal": ("journal_entry", "journal"),
    "question": ("appointment_question", "questions"),
    "medication": ("medication_event", "journal"),
    "lab": ("clinical_record", "labs"),
    "lab_document": ("lab_document", "labs"),
    "lab_review": ("clinical_record", "labs"),
    "import_review": ("clinical_record", "breathing"),
    "baseline": ("derived_snapshot", "body"),
    "draft": ("report_snapshot", "journal"),
    "snapshot": ("report_snapshot", "journal"),
    "settings": ("profile_revision", "body"),
}


def owner_context(request):
    context = AuthorizationContext(request)
    user, owner, grant = context.current()
    if not owner or user.pk != owner.pk or grant is not None:
        raise AccessDenied()
    return context, Patient.objects.get_or_create(owner=owner)[0]


def etag(record):
    return '"' + salted_hmac("record-version", f"{record.pk}:{record.version}").hexdigest() + '"'


def precondition(request, record):
    value = request.headers.get("If-Match")
    if not value:
        raise DomainError("precondition_required", 428)
    if value != etag(record):
        raise DomainError("revision_conflict", 412)


def dto(context, record, revision=None):
    if record.deleted_at:
        raise AccessDenied()
    user, owner, grant = context.current()
    if record.kind in {"lab_review", "import_review", "settings", "draft"} and (
        grant is not None or user.pk != record.patient.owner_id
    ):
        raise AccessDenied()
    revision = revision or record.current
    if revision is None:
        raise AccessDenied()
    blob, metadata, authorize = select(context, revision.blob_id)
    payload = json.loads(store.read(blob, metadata.identity, authorize))
    if payload.get("source_kind") and (
        not payload.get("record_status") or str(payload.get("metric_id", "")).startswith("blood_pressure_")
    ):
        # Project already-received phone records using the current server mapping.
        # Their immutable encrypted source evidence and source revision stay intact.
        from ingest.mapping import normalize

        _, _, _, payload = normalize({"kind": payload["source_kind"], "payload": payload})
    if record.kind == "baseline":
        dependencies = blob.dependencies.values("pk")
        payload["source_revisions_changed"] = (
            Record.objects.filter(revisions__blob__in=dependencies)
            .exclude(current__blob__in=dependencies)
            .exists()
        )
    if record.kind in {"journal", "question", "medication"}:
        payload["visibility"] = blob.visibility
    if grant and record.kind == "medication":
        payload.pop("note", None)
    if grant:
        for field in (
            "origin_record_id",
            "private_note",
            "source_filename",
            "source_location",
            "source_identity",
            "source_namespace",
            "owner_match_evidence",
            "linked_record_ids",
            "included_medication_ids",
            "parent_entry_id",
        ):
            payload.pop(field, None)
    return {
        "id": str(record.pk),
        "revision_id": str(revision.pk),
        "kind": record.kind,
        "version": revision.version,
        "etag": etag(record),
        "clinical_date": blob.clinical_date.isoformat() if blob.clinical_date else None,
        "received_at": revision.received_at.isoformat(),
        "data": payload,
    }


def replay(request):
    """Resolve a record mutation retry before mutable domain preconditions."""
    context, patient = owner_context(request)
    try:
        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except (ValueError, TypeError):
        raise DomainError("idempotency_key_required", 400) from None
    route = hashlib.sha256((request.method + request.path).encode()).hexdigest()
    prior = (
        Mutation.objects.filter(actor=request.user, key=key, route_digest=route)
        .select_related("record", "revision")
        .first()
    )
    if prior is None:
        return None
    digest = TransitKMS().identity_digest(
        patient.owner_id, "mutation", hashlib.sha256(request.body).hexdigest(), route, 1
    )
    if prior.body_digest != digest:
        raise DomainError("idempotency_conflict", 409)
    return dto(context, prior.record, prior.revision)


def save(
    request,
    kind,
    payload,
    day,
    record_id=None,
    visibility="private",
    dependencies=(),
    parent=None,
    commit_hook=None,
    prepare_hook=None,
    audience_grant=None,
):
    context, patient = owner_context(request)
    try:
        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except (ValueError, AttributeError):
        raise DomainError("idempotency_key_required", 400) from None
    route = hashlib.sha256((request.method + request.path).encode()).hexdigest()
    digest = TransitKMS().identity_digest(
        patient.owner_id, "mutation", hashlib.sha256(request.body).hexdigest(), route, 1
    )
    prior = (
        Mutation.objects.filter(actor=request.user, key=key, route_digest=route)
        .select_related("record", "revision")
        .first()
    )
    if prior:
        if prior.body_digest != digest:
            raise DomainError("idempotency_conflict", 409)
        return dto(context, prior.record, prior.revision)
    record = (
        Record.objects.filter(pk=record_id, patient=patient, deleted_at__isnull=True).first()
        if record_id
        else Record(patient=patient, kind=kind)
    )
    if record is None or record.kind != kind:
        raise AccessDenied()
    if record_id:
        precondition(request, record)
    initial_epoch = context.epoch()
    prepared_commit = prepare_hook(record) if prepare_hook else None
    old_version = record.version
    revision_id, blob_id = uuid.uuid4(), uuid.uuid4()
    envelope_kind, category = KINDS[kind]
    if kind == "baseline" and payload.get("metric_id") != "weight":
        category = "breathing"
    identity = Identity(patient.owner_id, envelope_kind, record.pk, blob_id, 1)
    reference = RecordRef(identity, category, day, visibility)
    blob_name, checksum, size = store.write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
        identity,
        context.envelope_authorizer(reference, "write"),
    )
    permission_changed = False
    with transaction.atomic():
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        context.require(reference, "write")
        prior = Mutation.objects.filter(actor=request.user, key=key, route_digest=route).first()
        if prior:
            if prior.body_digest != digest:
                raise DomainError("idempotency_conflict", 409)
            record, revision = prior.record, prior.revision
        else:
            if record_id:
                record = Record.objects.select_for_update().get(pk=record_id)
                if record.deleted_at or record.version != old_version:
                    raise DomainError("revision_conflict", 412)
            else:
                record.save()
            if parent and parent.owner_id != patient.owner_id:
                raise AccessDenied()
            for dep in dependencies:
                context.require(
                    __import__("artifacts.selectors", fromlist=["reference"]).reference(dep)
                )
            blob = SecureRecord.objects.create(
                id=blob_id,
                object_id=record.pk,
                owner_id=patient.owner_id,
                kind=envelope_kind,
                category=category,
                clinical_date=day,
                visibility=visibility,
                owner_only=kind in {"lab_review", "import_review", "settings", "draft"}
                or (kind == "snapshot" and audience_grant is None),
                audience_grant=audience_grant,
                parent=parent,
                blob_name=blob_name,
                ciphertext_sha256=checksum,
                ciphertext_bytes=size,
            )
            blob.dependencies.set(dependencies)
            revision = Revision.objects.create(
                id=revision_id,
                record=record,
                version=old_version + 1,
                blob=blob,
                measured_start=payload.get("measured_start"),
            )
            record.current, record.version = revision, old_version + 1
            record.save(update_fields=["current", "version"])
            if prepared_commit:
                prepared_commit(record, revision, patient)
            if commit_hook:
                commit_hook(record, revision, patient)
            Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
            Mutation.objects.create(
                actor=request.user,
                key=key,
                route_digest=route,
                body_digest=digest,
                record=record,
                revision=revision,
            )
            from jobs.service import enqueue

            enqueue("invalidate", record.pk, record.version)
            audit.emit("record_saved", request.user, record.pk)
            if (
                record_id
                and visibility == "private"
                and SecureRecord.objects.filter(object_id=record.pk, visibility="shared").exists()
            ):
                SecureRecord.objects.filter(object_id=record.pk).update(visibility="private")
                Account.objects.filter(pk=patient.owner_id).update(
                    sharing_epoch=F("sharing_epoch") + 1
                )
                ledger.enqueue(patient.owner_id, "record_private", record.pk)
                permission_changed = True
    if permission_changed or context.epoch() != initial_epoch:
        return {
            "operation_id": str(revision.pk),
            "status": "saved",
            "context_reset_required": True,
            "next_permission_epoch": context.epoch(),
        }
    return dto(context, record, revision)


def permitted(request, kinds, start=None, end=None, limit=50, after=None, phone_only=False):
    context = AuthorizationContext(request)
    _, owner, grant = context.current()
    if not owner:
        raise AccessDenied()
    query = Record.objects.filter(
        patient__owner=owner,
        kind__in=kinds,
        deleted_at__isnull=True,
        superseded_at__isnull=True,
        current__isnull=False,
    ).select_related("current__blob")
    if phone_only:
        query = query.filter(sourceidentity__isnull=False)
    visibility = request.GET.get("visibility")
    if visibility is not None and set(kinds) <= {"journal", "question", "medication"}:
        if visibility not in {"private", "shared"}:
            raise DomainError("invalid_visibility")
        query = query.filter(current__blob__visibility=visibility)
    if start:
        query = query.filter(current__blob__clinical_date__gte=start)
    if end:
        query = query.filter(current__blob__clinical_date__lte=end)
    if grant:
        query = query.filter(current__blob__clinical_date__range=(grant.starts_on, grant.ends_on))
    from datetime import date

    from .pagination import window

    if start and end:
        start_day = date.fromisoformat(str(start))
        end_day = date.fromisoformat(str(end))
        if not 0 <= (end_day - start_day).days < 366:
            raise DomainError("invalid_date_range")
    limit = min(max(int(limit), 1), 200)
    filters = {key: value for key, value in request.GET.items() if key != "cursor"}
    if request.method == "POST":
        from .validation import parse_json

        filters.update(
            {key: value for key, value in parse_json(request.body).items() if key != "cursor"}
        )
    query, make_cursor = window(query, context, kinds, start, end, after, limit, filters)
    candidates = list(query)
    result = []
    last = None
    consumed = 0
    for record in candidates[: max(200, limit)]:
        last = record
        consumed += 1
        try:
            result.append(dto(context, record))
        except AccessDenied:
            continue
        if len(result) >= limit:
            break
    cursor = make_cursor(last) if last and consumed < len(candidates) else None
    return {"items": result, "cursor": cursor}


def delete(request, record_id):
    from .actions import Command

    command = Command(request)
    return command.run(lambda: _delete(request, record_id))


@transaction.atomic
def _delete(request, record_id):
    context, patient = owner_context(request)
    Patient.objects.select_for_update().get(pk=patient.pk)
    record = (
        Record.objects.select_for_update()
        .filter(pk=record_id, patient=patient, deleted_at__isnull=True)
        .first()
    )
    if not record:
        raise AccessDenied()
    precondition(request, record)
    from ingest.models import SourceIdentity, SourceTombstone

    for source_identity in SourceIdentity.objects.filter(record=record):
        SourceTombstone.objects.get_or_create(
            source=source_identity.source,
            identity_digest=source_identity.digest,
            lookup_version=source_identity.lookup_version,
        )
    now = timezone.now()
    from .models import Designation

    Designation.objects.filter(record=record).update(record=None, version=F("version") + 1)
    record.deleted_at = now
    record.save(update_fields=["deleted_at"])
    blobs = SecureRecord.objects.filter(object_id=record.pk)
    ids = list(blobs.values_list("pk", flat=True))
    # Revoke immutable derived evidence too, including transitive dependencies.
    frontier = set(ids)
    while frontier:
        children = set(
            SecureRecord.objects.filter(
                Q(dependencies__pk__in=frontier) | Q(parent_id__in=frontier)
            ).values_list("pk", flat=True)
        ) - set(ids)
        ids.extend(children)
        frontier = children
    SecureRecord.objects.filter(pk__in=ids).update(
        deleted_at=now, purge_after=now + timedelta(hours=24)
    )
    Account.objects.filter(pk=patient.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
    Patient.objects.filter(pk=patient.pk).update(source_epoch=F("source_epoch") + 1)
    ledger.enqueue(patient.owner_id, "record_deleted", record.pk)
    audit.emit("record_deleted", request.user, record.pk)
    return {
        "status": "accepted",
        "context_reset_required": True,
        "next_permission_epoch": context.epoch(),
    }
