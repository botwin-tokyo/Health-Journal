"""Automatic, bounded display repair for pressure readings accepted before support existed."""

import json

from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity
from django.db import transaction
from django.utils import timezone
from jobs.models import Job
from jobs.service import enqueue
from records.models import Record
from records.validation import DomainError

from .canonical import authorizer
from .mapping import normalize
from .models import IngestBatch, SourceVersion

KIND = "bp_display_v1"
METRICS = {"blood_pressure_systolic", "blood_pressure_diastolic", "blood_pressure_pulse"}


def schedule():
    # Durable job identity prevents repeated work across worker restarts. Bound each poll.
    scheduled = Job.objects.filter(kind=KIND).values("reference")
    batches = (
        IngestBatch.objects.filter(state="processed", evidence__deleted_at__isnull=True)
        .exclude(pk__in=scheduled)
        .order_by("received_at", "pk")
        .values_list("pk", flat=True)[:16]
    )
    for identifier in batches:
        enqueue(KIND, identifier, 1)


def execute(job):
    batch = (
        IngestBatch.objects.select_related("source__device__owner", "evidence")
        .filter(pk=job.reference, state="processed", evidence__deleted_at__isnull=True)
        .first()
    )
    if batch is None:
        return
    receipts = list(batch.receipts.filter(outcome="accepted", revision_id__isnull=False))
    if not receipts:
        return
    blob = batch.evidence
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
    body = json.loads(store.read(blob, identity, authorizer(batch.source, identity)))
    for receipt in receipts:
        item = body["items"][receipt.ordinal]
        if (
            item["operation"] != "upsert"
            or item["kind"] != "scalar_observation"
            or item["payload"].get("metric_id") not in METRICS
        ):
            continue
        kind, category, day, data = normalize(item)
        with transaction.atomic():
            lease = Job.objects.select_for_update().get(pk=job.pk)
            if (
                lease.state != "running"
                or lease.lease_token != job.lease_token
                or lease.lease_until <= timezone.now()
            ):
                raise DomainError("lease_lost", 503)
            # A newer revision, deletion or supersession always wins over historical work.
            record = (
                Record.objects.select_for_update()
                .filter(
                    pk=receipt.record_id,
                    current_id=receipt.revision_id,
                    kind="observation",
                    deleted_at__isnull=True,
                    superseded_at__isnull=True,
                )
                .select_related("current")
                .first()
            )
            if record is None:
                continue
            record.kind = kind
            record.save(update_fields=["kind"])
            SecureRecord.objects.filter(pk=record.current.blob_id).update(
                category=category,
                clinical_date=day,
                owner_only=not data["clinical_eligible"],
            )
            SourceVersion.objects.filter(revision_id=receipt.revision_id).update(
                disposition=data["record_status"],
            )
            receipt.disposition = data["record_status"]
            receipt.save(update_fields=["disposition"])
