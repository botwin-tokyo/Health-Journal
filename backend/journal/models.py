from django.db import models


class MedicationLink(models.Model):
    entry = models.ForeignKey(
        "records.Record", on_delete=models.PROTECT, related_name="medication_links"
    )
    event = models.ForeignKey(
        "records.Record", on_delete=models.PROTECT, related_name="entry_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "event"], name="entry_medication_link_unique")
        ]
