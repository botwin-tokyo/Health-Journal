"""Restartable, bounded identity indexing; never decrypt deleted evidence."""

import json

from access.policy import AggregateAuthorizationContext
from artifacts import store
from artifacts.selectors import select
from crypto.envelopes import TransitKMS
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from records.models import Patient

from ingest import lookups
from ingest.models import SourceIdentity


class Command(BaseCommand):
    help = (
        "Populate dual source lookup indexes from authorized retained evidence. No key retirement."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise CommandError("Limit must be 1..1000")
        versions = lookups.versions()
        indexed = 0
        target = max(versions)
        rows = (
            SourceIdentity.objects.exclude(lookups__lookup_version=target)
            .select_related("source__device", "record__current__blob", "record__patient")
            .order_by("pk")
        )
        for row in rows.filter(record__deleted_at__isnull=True, source__disabled_at__isnull=True)[
            :limit
        ]:
            if row.record.current_id is None:
                continue
            context = AggregateAuthorizationContext(row.record.patient.owner_id)
            blob, metadata, authorize = select(context, row.record.current.blob_id)
            payload = json.loads(store.read(blob, metadata.identity, authorize))
            if (
                payload.get("source_namespace") != str(row.source.namespace)
                or payload.get("source_kind") != row.kind
            ):
                raise CommandError("Source provenance mismatch; indexing stopped")
            values = lookups.digests(TransitKMS(), row.source, row.kind, payload["source_identity"])
            if values[1] != row.digest:
                raise CommandError("Source identity mismatch; indexing stopped")
            with transaction.atomic():
                Patient.objects.select_for_update().get(pk=row.record.patient_id)
                context.current()
                lookups.index(row, values)
            indexed += 1
        remaining = rows.count()
        self.stdout.write(
            json.dumps(
                {
                    "indexed": indexed,
                    "remaining": remaining,
                    "lookup_versions": versions,
                    "old_key_retirement_allowed": False,
                }
            )
        )
