import hashlib
import io

from artifacts import store
from artifacts.models import SecureRecord
from crypto.envelopes import Identity, TransitKMS
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from labs.models import LabReport

from records.models import Patient


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.ENVIRONMENT not in {"development", "test"} or not settings.DATABASES["default"][
            "NAME"
        ].startswith("health03_capacity_"):
            raise CommandError("Synthetic capacity database required")
        patient = Patient.objects.get(owner__email="capacity@example.invalid")
        if LabReport.objects.filter(patient=patient).count() == 100:
            self.stdout.write("100 encrypted mixed PDF fixtures already present")
            return
        if LabReport.objects.filter(patient=patient).exists():
            raise CommandError("Partial fixture requires explicit resume review")
        import json

        from parser_service.operations import render_report
        from PIL import Image, ImageDraw, ImageFont
        from pypdf import PdfReader, PdfWriter

        text = render_report(
            json.dumps(
                {
                    "template": "appointment-v1",
                    "sections": [
                        {
                            "heading": "Synthetic laboratory fixture",
                            "text": "Fictional analyte: <5 mg/L. No personal information.",
                        }
                    ],
                }
            ).encode()
        )
        image = Image.new("RGB", (1200, 1600), "white")
        draw = ImageDraw.Draw(image)
        draw.text(
            (80, 100),
            "SYNTHETIC LABORATORY\nFictional analyte: less than 5 mg/L",
            fill="black",
            font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32),
        )
        scanned = io.BytesIO()
        image.save(scanned, format="PDF", resolution=150)
        for index in range(100):
            writer = PdfWriter()
            writer.append(PdfReader(io.BytesIO(text if index % 2 == 0 else scanned.getvalue())))
            writer.add_metadata({"/SyntheticFixture": str(index)})
            output = io.BytesIO()
            writer.write(output)
            payload = output.getvalue()
            blob = SecureRecord(
                owner_id=patient.owner_id,
                kind="lab_document",
                category="labs",
                clinical_date=None,
                mime_type="application/pdf",
            )
            identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)

            def authorize(selected, action):
                return selected == identity and action == "write"

            blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
                payload, identity, authorize
            )
            digest = TransitKMS().identity_digest(
                patient.owner_id, "original-pdf", hashlib.sha256(payload).hexdigest(), "labs", 1
            )
            blob.save()
            LabReport.objects.create(patient=patient, original=blob, content_digest=digest)
        self.stdout.write(
            "100 original encrypted PDF fixtures: 50 text, 50 scanned; quarantined, not auto-published."
        )
