import uuid

from django.db import models


class MeasurementImport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey("records.Patient", on_delete=models.PROTECT)
    original = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    content_digest = models.CharField(max_length=100)
    parser_job = models.ForeignKey("artifacts.SecurityJob", on_delete=models.PROTECT)
    review = models.ForeignKey("records.Record", null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default="quarantined")
    version = models.PositiveIntegerField(default=1)
    committed_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["patient", "content_digest"], name="patient_csv_unique")
        ]
