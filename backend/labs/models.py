import uuid

from django.db import models


class LabReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey("records.Patient", on_delete=models.PROTECT)
    original = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    content_digest = models.CharField(max_length=100)
    parser_job = models.ForeignKey("artifacts.SecurityJob", null=True, on_delete=models.PROTECT)
    review = models.ForeignKey("records.Record", null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default="quarantined")
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="corrections"
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "content_digest"], name="patient_original_pdf_unique"
            )
        ]


class PublishedResult(models.Model):
    series_id = models.CharField(max_length=64, blank=True, db_index=True)
    superseded_at = models.DateTimeField(null=True)
    report = models.ForeignKey(
        LabReport, on_delete=models.PROTECT, related_name="published_results"
    )
    record = models.OneToOneField("records.Record", on_delete=models.PROTECT)
    review_revision = models.ForeignKey("records.Revision", on_delete=models.PROTECT)
