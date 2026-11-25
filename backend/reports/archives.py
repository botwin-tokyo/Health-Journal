import csv
import io
import json
from datetime import timedelta

from access.policy import AccessDenied, JobAuthorizationContext
from accounts.policy import fresh, session_state
from artifacts import store
from artifacts.models import SecureRecord
from artifacts.selectors import select
from crypto.envelopes import Identity
from django.db import transaction
from django.utils import timezone
from jobs.models import Job
from jobs.service import enqueue
from parser_service.operations import csv_cell
from records import service
from records.actions import Command
from records.http import endpoint
from records.models import Record, Revision
from records.validation import DomainError, parse_json

from .models import ExportBundle, ExportPart


@endpoint({"POST"})
def create(request):
    command = Command(request)
    previous = command.previous()
    if previous:
        return previous
    state = session_state(request)
    if not fresh(state):
        raise DomainError("reauthentication_required", 403)
    body = parse_json(request.body)
    format = body.get("format")
    if format not in {"body_csv", "breathing_session", "owner_archive"}:
        raise DomainError("invalid_export_format")
    query = Record.objects.filter(
        patient=command.patient, deleted_at__isnull=True, current__isnull=False
    )
    if format == "body_csv":
        query = query.filter(kind="weight")
    if format == "breathing_session":
        query = query.filter(kind="pulmonary", pk=body.get("record_id"))
    if body.get("record_ids") is not None:
        if not isinstance(body["record_ids"], list) or len(body["record_ids"]) > 1000:
            raise DomainError("invalid_export_selection")
        query = query.filter(pk__in=body["record_ids"])
    if body.get("from"):
        query = query.filter(current__blob__clinical_date__gte=body["from"])
    if body.get("to"):
        query = query.filter(current__blob__clinical_date__lte=body["to"])
    if format == "owner_archive":
        revisions = list(
            Revision.objects.filter(record__in=query, blob__deleted_at__isnull=True)
            .order_by("record_id", "version")
            .values_list("pk", flat=True)[:500001]
        )
    else:
        revisions = list(query.order_by("id").values_list("current_id", flat=True)[:500001])
    if len(revisions) > 500000:
        raise DomainError("export_scope_too_large")
    documents = []
    if format == "owner_archive":
        from labs.models import LabReport

        documents = [
            {
                "id": str(report.original_id),
                "document_id": str(report.original.object_id),
                "state": report.state,
            }
            for report in LabReport.objects.filter(
                patient=command.patient, original__deleted_at__isnull=True
            ).select_related("original")[:10001]
        ]
        if len(documents) > 10000:
            raise DomainError("export_scope_too_large")
    payload = json.dumps(
        {
            "schema_version": 1,
            "format": format,
            "revisions": [str(value) for value in revisions],
            "documents": documents,
            "current_revisions": {
                str(key): str(value) for key, value in query.values_list("pk", "current_id")
            }
            if format == "owner_archive"
            else {},
        }
    ).encode()
    blob = SecureRecord(
        owner_id=command.patient.owner_id,
        kind="report_snapshot",
        category="journal",
        clinical_date=None,
        owner_only=True,
    )
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)

    def authorize(selected, action):
        service.owner_context(request)
        return identity == selected and action == "write"

    blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
        payload, identity, authorize
    )

    def commit():
        blob.save()
        bundle = ExportBundle.objects.create(
            owner_id=command.patient.owner_id,
            actor=request.user,
            session_hash=state.pk,
            permission_epoch=command.context.epoch(),
            format=format,
            manifest=blob,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        enqueue("archive", bundle.pk, 1)
        return {"id": str(bundle.pk), "state": "queued"}

    return command.run(commit)


def execute(job):
    bundle = ExportBundle.objects.get(pk=job.reference)
    if bundle.expires_at <= timezone.now():
        raise DomainError("export_expired", 403)
    context = JobAuthorizationContext(bundle.actor_id, bundle.session_hash, None)
    if context.epoch() != bundle.permission_epoch:
        raise AccessDenied()
    blob, metadata, authorize = select(context, bundle.manifest_id)
    manifest = json.loads(store.read(blob, metadata.identity, authorize))
    ExportBundle.objects.filter(pk=bundle.pk).update(state="running")
    buffer = []
    dependencies = []
    size = 2
    ordinal = 0

    def publish(encoded=None, mime=None):
        nonlocal buffer, dependencies, size, ordinal
        if encoded is not None:
            pass
        elif not buffer:
            return
        elif bundle.format == "body_csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "record_id",
                    "revision_id",
                    "clinical_date",
                    "original_value",
                    "original_unit",
                    "canonical_kg",
                    "source_type",
                ]
            )
            for row in buffer:
                data = row["data"]
                writer.writerow(
                    [
                        row["id"],
                        row["revision_id"],
                        row["clinical_date"],
                        csv_cell(data["value"], numeric=True),
                        csv_cell(data["unit"]),
                        csv_cell(data["canonical_value"], numeric=True),
                        csv_cell(data["source_type"]),
                    ]
                )
            encoded = output.getvalue().encode()
            mime = "text/csv"
        else:
            encoded = json.dumps(
                {"schema_version": 1, "records": buffer}, ensure_ascii=False, separators=(",", ":")
            ).encode()
            mime = "application/json"
        if len(encoded) > 25 * 1024 * 1024:
            raise DomainError("export_part_too_large")
        output = SecureRecord(
            owner=bundle.owner,
            kind="report_snapshot",
            category="journal",
            clinical_date=None,
            owner_only=True,
            mime_type=mime,
        )
        identity = Identity(output.owner_id, output.kind, output.object_id, output.pk, 1)

        def allow(selected, action):
            if (
                selected != identity
                or action != "write"
                or context.epoch() != bundle.permission_epoch
            ):
                raise AccessDenied()
            for dependency in dependencies:
                select(context, dependency.pk)
            return True

        output.blob_name, output.ciphertext_sha256, output.ciphertext_bytes = store.write(
            encoded, identity, allow
        )
        with transaction.atomic():
            lease = Job.objects.select_for_update().get(pk=job.pk)
            if (
                lease.state != "running"
                or lease.lease_token != job.lease_token
                or lease.lease_until <= timezone.now()
            ):
                raise DomainError("lease_lost", 503)
            allow(identity, "write")
            if not ExportPart.objects.filter(bundle=bundle, ordinal=ordinal).exists():
                output.save()
                output.dependencies.set(dependencies)
                ExportPart.objects.create(
                    bundle=bundle, ordinal=ordinal, blob=output, bytes=len(encoded)
                )
        ordinal += 1
        buffer = []
        dependencies = []
        size = 2

    for identifier in manifest["revisions"]:
        revision = Revision.objects.select_related("record__patient", "blob").get(pk=identifier)
        value = service.dto(context, revision.record, revision)
        if bundle.format == "owner_archive":
            value["revision_relationships"] = {
                "current_at_export": manifest.get("current_revisions", {}).get(
                    str(revision.record_id)
                ),
                "previous_revision_id": str(previous)
                if (
                    previous := Revision.objects.filter(
                        record=revision.record, version__lt=revision.version
                    )
                    .order_by("-version")
                    .values_list("pk", flat=True)
                    .first()
                )
                else None,
                "dependencies": [
                    str(value) for value in revision.blob.dependencies.values_list("pk", flat=True)
                ],
            }
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > 24 * 1024 * 1024:
            raise DomainError("export_record_too_large")
        if size + len(encoded) > 24 * 1024 * 1024 or len(buffer) >= 100:
            publish()
        buffer.append(value)
        dependencies.append(revision.blob)
        size += len(encoded) + 1
    publish()
    for document in manifest.get("documents", []):
        original, metadata, authorize = select(context, document["id"], "read_original_document")
        encoded = store.read(original, metadata.identity, authorize)
        dependencies = [original]
        publish(encoded, "application/octet-stream")
    dependencies = [bundle.manifest]
    publish(
        json.dumps(
            {
                "schema_version": 1,
                "format": bundle.format,
                "record_revisions": manifest["revisions"],
                "documents": manifest.get("documents", []),
                "data_parts": ordinal,
            },
            separators=(",", ":"),
        ).encode(),
        "application/json",
    )
    if context.epoch() != bundle.permission_epoch:
        raise AccessDenied()
    with transaction.atomic():
        lease = Job.objects.select_for_update().get(pk=job.pk)
        if (
            lease.state != "running"
            or lease.lease_token != job.lease_token
            or lease.lease_until <= timezone.now()
        ):
            raise DomainError("lease_lost", 503)
        ExportBundle.objects.filter(pk=bundle.pk).update(state="ready")
