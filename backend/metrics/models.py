from django.db import models


class RetiredReference(models.Model):
    record = models.OneToOneField("records.Record", on_delete=models.PROTECT)
    retired_at = models.DateTimeField(auto_now_add=True)


class AggregateState(models.Model):
    patient = models.OneToOneField("records.Patient", on_delete=models.PROTECT)
    computed_epoch = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class AggregateSnapshot(models.Model):
    patient = models.ForeignKey("records.Patient", on_delete=models.PROTECT)
    clinical_date = models.DateField()
    metric = models.CharField(max_length=40)
    slot = models.CharField(max_length=16, default="")
    method = models.CharField(max_length=24)
    source_epoch = models.PositiveBigIntegerField()
    blob = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "clinical_date", "metric", "slot", "method", "source_epoch"],
                name="aggregate_snapshot_inputs_unique",
            )
        ]
