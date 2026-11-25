import json
import uuid
from pathlib import Path

from accounts.models import Account
from artifacts import store
from artifacts.models import SecureRecord
from body.service import weight
from crypto.envelopes import Identity
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from records.models import Designation, Patient, Record, Revision


class Command(BaseCommand):
    help = "Seed deterministic fictional encrypted weight history. Never enrolls a working login."

    def add_arguments(self, parser):
        parser.add_argument("--environment", required=True, choices=["development"])

    def handle(self, *args, **options):
        if settings.ENVIRONMENT != "development":
            raise CommandError("Synthetic seed refuses this environment")
        email = "fixture-owner@example.invalid"
        if Account.objects.exclude(email=email).exists():
            raise CommandError("Synthetic seed requires a separate empty development namespace")
        owner, _ = Account.objects.get_or_create(
            email=email,
            defaults={"role": "owner", "is_active": False, "enrollment_complete": False},
        )
        if owner.is_active or owner.enrollment_complete:
            raise CommandError("Synthetic fixture account must remain inactive")
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
        patient, _ = Patient.objects.get_or_create(owner=owner)
        fixture = json.loads(
            (
                Path(__file__).resolve().parents[4] / "tests/fixtures/synthetic/backend-v1.json"
            ).read_text()
        )
        for raw in fixture["weights"]:
            identifier = uuid.UUID(raw["id"])
            if Record.objects.filter(pk=identifier).exists():
                continue
            payload, day = weight({key: value for key, value in raw.items() if key != "id"})
            blob = SecureRecord(
                owner=owner,
                object_id=identifier,
                kind="clinical_record",
                category="body",
                clinical_date=day,
            )
            identity = Identity(owner.pk, blob.kind, identifier, blob.pk, 1)

            def authorize(selected, action):
                return (
                    settings.ENVIRONMENT == "development"
                    and selected == identity
                    and action == "write"
                    and not owner.is_active
                )

            blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
                json.dumps(payload).encode(), identity, authorize
            )
            with transaction.atomic():
                Patient.objects.select_for_update().get(pk=patient.pk)
                if Record.objects.filter(pk=identifier).exists():
                    continue
                blob.save()
                record = Record.objects.create(id=identifier, patient=patient, kind="weight")
                revision = Revision.objects.create(record=record, version=1, blob=blob)
                record.current, record.version = revision, 1
                record.save()
                Designation.objects.get_or_create(
                    patient=patient,
                    clinical_date=day,
                    domain="body",
                    slot="",
                    defaults={"record": record},
                )
        from datetime import date

        from records.service import KINDS
        from records.synthetic import supplemental_records

        for identifier, kind, payload in supplemental_records():
            if Record.objects.filter(pk=identifier).exists():
                continue
            envelope_kind, category = KINDS[kind]
            blob = SecureRecord(
                owner=owner,
                object_id=identifier,
                kind=envelope_kind,
                category=category,
                clinical_date=date(2026, 11, 7),
                owner_only=kind == "settings",
            )
            identity = Identity(owner.pk, envelope_kind, identifier, blob.pk, 1)

            def authorize(selected, action):
                return (
                    selected == identity
                    and action == "write"
                    and settings.ENVIRONMENT == "development"
                    and not Account.objects.get(pk=owner.pk).is_active
                )

            blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
                json.dumps(payload).encode(), identity, authorize
            )
            with transaction.atomic():
                Patient.objects.select_for_update().get(pk=patient.pk)
                if Record.objects.filter(pk=identifier).exists():
                    continue
                blob.save()
                record = Record.objects.create(id=identifier, patient=patient, kind=kind, version=1)
                revision = Revision.objects.create(
                    record=record,
                    version=1,
                    blob=blob,
                    measured_start=payload.get("measured_start"),
                )
                record.current = revision
                record.save(update_fields=["current"])
                if kind == "pulmonary":
                    Designation.objects.get_or_create(
                        patient=patient,
                        clinical_date=date(2026, 11, 7),
                        domain="breathing",
                        slot="morning",
                        defaults={"record": record},
                    )
        self.stdout.write("Fictional encrypted fixture seeded; account remains inactive.")
