"""Repair current display indexes from accepted batches; never replay or resurrect data."""

import json
from collections import Counter

from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity
from django.core.management.base import BaseCommand
from django.db import transaction
from records.models import Record

from ingest.canonical import authorizer
from ingest.contract import registry
from ingest.mapping import normalize, select_imported
from ingest.models import IngestBatch, SourceVersion


class Command(BaseCommand):
    help = "Reindex existing accepted phone records against the shipped phone field mapping"

    def handle(self, *args, **options):
        counts = Counter()
        batches = IngestBatch.objects.filter(
            state="processed", evidence__deleted_at__isnull=True
        ).select_related("source__device__owner", "evidence")
        for batch in batches.iterator():
            receipts = {
                r.ordinal: r
                for r in batch.receipts.filter(outcome="accepted", revision_id__isnull=False)
            }
            if not receipts:
                continue
            blob = batch.evidence
            identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
            body = json.loads(store.read(blob, identity, authorizer(batch.source, identity)))
            for ordinal, receipt in receipts.items():
                item = body["items"][ordinal]
                if item["operation"] != "upsert":
                    continue
                if (
                    item["kind"] == "scalar_observation"
                    and item["payload"].get("metric_id") not in registry()["body_metrics"]
                    and item["payload"].get("metric_id") not in {
                        "blood_pressure_systolic", "blood_pressure_diastolic", "blood_pressure_pulse"
                    }
                ):
                    continue
                record = (
                    Record.objects.select_related("current__blob", "patient")
                    .filter(
                        pk=receipt.record_id,
                        current_id=receipt.revision_id,
                        deleted_at__isnull=True,
                    )
                    .first()
                )
                if not record:
                    continue
                kind, category, day, data = normalize(item)
                with transaction.atomic():
                    locked = Record.objects.select_for_update().get(pk=record.pk)
                    if locked.deleted_at or locked.current_id != receipt.revision_id:
                        continue
                    record.kind = kind
                    record.save(update_fields=["kind"])
                    SecureRecord.objects.filter(pk=record.current.blob_id).update(
                        category=category,
                        clinical_date=day,
                        owner_only=kind in {"body_context", "source_record"}
                        or not data["clinical_eligible"],
                    )
                    SourceVersion.objects.filter(revision_id=receipt.revision_id).update(
                        disposition=data["record_status"]
                    )
                    receipt.disposition = data["record_status"]
                    receipt.save(update_fields=["disposition"])
                    select_imported(record, record.current, data, day)
                counts[kind] += 1
        self.stdout.write(json.dumps(dict(counts), sort_keys=True))
