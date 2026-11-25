"""Actual encrypted deployment-size fixture and authenticated warm read measurements."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from accounts.models import Account
from allauth.account.models import EmailAddress
from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from records.models import Patient, Record, Revision
from records.service import KINDS


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--samples", type=int, default=35040)
        parser.add_argument("--measure-only", action="store_true")

    def handle(self, *args, **options):
        if settings.ENVIRONMENT not in {"development", "test"} or not settings.DATABASES["default"][
            "NAME"
        ].startswith("health03_capacity_"):
            raise CommandError("Capacity fixture requires a separate synthetic capacity database")
        email = "capacity@example.invalid"
        if Account.objects.exclude(email=email).exists():
            raise CommandError("Not a synthetic capacity namespace")
        owner, created = Account.objects.get_or_create(
            email=email, defaults={"role": "owner", "enrollment_complete": True}
        )
        password = "Synthetic-capacity-only!6912"
        if created:
            owner.set_password(password)
            owner.save()
        EmailAddress.objects.get_or_create(
            user=owner, email=email, defaults={"verified": True, "primary": True}
        )
        patient, _ = Patient.objects.get_or_create(owner=owner)
        start = datetime(2025, 11, 8, tzinfo=timezone.utc)
        total = options["samples"] + 1095 + 365 + 100
        begun = time.monotonic()
        for index in range(0 if options["measure_only"] else total):
            identifier = uuid.uuid5(uuid.NAMESPACE_URL, "health03-capacity-" + str(index))
            if Record.objects.filter(pk=identifier).exists():
                continue
            instant = start + timedelta(minutes=15 * (index % options["samples"]))
            day = instant.date()
            common = {
                "synthetic_only": True,
                "clinical_date": str(day),
                "time_precision": "second",
                "measured_start": instant.isoformat(),
                "timezone": "UTC",
                "original_offset_minutes": 0,
                "validity": "valid",
                "source_type": "manual",
            }
            if index < options["samples"]:
                kind = "observation"
                payload = {
                    **common,
                    "metric_id": "bpm",
                    "value": "68",
                    "unit": "beats/min",
                    "source_type": "direct_device",
                    "statistic": "requested_sample",
                    "qualification": "reported",
                }
            elif index < options["samples"] + 1095:
                kind = "pulmonary"
                payload = {
                    **common,
                    "slot": "morning",
                    "capture_status": "not_applicable",
                    "values": {"fev1": "3.82", "fvc": "4.87"},
                    "units": {"fev1": "L", "fvc": "L"},
                    "selected_trial_id": str(identifier),
                    "curves": {
                        "synthetic_only": True,
                        "samples": [[str(n / 10), str(n / 100)] for n in range(100)],
                    },
                }
            elif index < total - 100:
                kind = "journal"
                payload = {
                    **common,
                    "text": "Fictional capacity journal entry",
                    "visibility": "private",
                }
            else:
                kind = "lab"
                payload = {
                    **common,
                    "label": "Fictional result",
                    "value_kind": "numeric",
                    "value": "5",
                    "operator": "lt",
                    "raw_result_text": "<5",
                    "unit": "mg/L",
                    "review_status": "reviewed",
                }
            envelope_kind, category = KINDS[kind]
            blob = SecureRecord(
                owner=owner,
                object_id=identifier,
                kind=envelope_kind,
                category=category,
                clinical_date=day,
            )
            identity = Identity(owner.pk, envelope_kind, identifier, blob.pk, 1)

            def authorize(selected, action):
                return selected == identity and action == "write"

            blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
                json.dumps(payload).encode(), identity, authorize
            )
            from django.db import transaction

            with transaction.atomic():
                blob.save()
                record = Record.objects.create(id=identifier, patient=patient, kind=kind, version=1)
                revision = Revision.objects.create(
                    record=record, version=1, blob=blob, measured_start=instant
                )
                record.current = revision
                record.save(update_fields=["current"])
            if index % 1000 == 0:
                self.stdout.write(f"Encrypted synthetic records: {index}/{total}")
                self.stdout.flush()
        client = Client(HTTP_HOST="api.health03.test")
        response = client.post(
            "/_allauth/browser/v1/auth/login",
            {"email": email, "password": password},
            content_type="application/json",
            secure=True,
        )
        if response.status_code != 200:
            raise CommandError("Synthetic session login failed")
        import logging

        logging.getLogger("health03.requests").disabled = True
        results = {}
        for path in [
            "/api/v1/body?date=2026-11-07",
            "/api/v1/breathing?date=2025-11-08",
            "/api/v1/sleep-activity?date=2025-11-08",
            "/api/v1/journal/entries",
            "/api/v1/labs/trends",
            "/api/v1/labs/reports",
        ]:
            durations = []
            for attempt in range(21):
                tick = time.monotonic()
                response = client.get(path, secure=True)
                duration = time.monotonic() - tick
                if response.status_code != 200:
                    raise CommandError("Read model failed: " + path)
                if attempt:
                    durations.append(duration)
            results[path] = {"p95_seconds": sorted(durations)[18], "samples": len(durations)}
        report = {
            "synthetic_only": True,
            "machine": "actual Raspberry Pi",
            "encrypted_records": Record.objects.count(),
            "requested_hr_samples": options["samples"],
            "pulmonary_sessions": 1095,
            "journal_entries": 365,
            "structured_lab_results": 100,
            "mixed_pdf_fixtures": __import__(
                "labs.models", fromlist=["LabReport"]
            ).LabReport.objects.count(),
            "elapsed_seconds": round(time.monotonic() - begun, 2),
            "reads": results,
            "read_target_met": all(row["p95_seconds"] < 2 for row in results.values()),
        }
        Path(options["output"]).write_text(json.dumps(report, indent=2) + "\n")
        self.stdout.write(json.dumps(report))
        if not report["read_target_met"]:
            raise CommandError("Capacity read target not met")
