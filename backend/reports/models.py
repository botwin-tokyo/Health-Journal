import uuid

from django.conf import settings
from django.db import models


class ExportBundle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="export_bundles"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_bundles"
    )
    session_hash = models.CharField(max_length=64)
    permission_epoch = models.CharField(max_length=64)
    format = models.CharField(max_length=24)
    manifest = models.ForeignKey("artifacts.SecureRecord", on_delete=models.PROTECT)
    state = models.CharField(max_length=16, default="queued")
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class ExportPart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bundle = models.ForeignKey(ExportBundle, on_delete=models.PROTECT, related_name="parts")
    ordinal = models.PositiveIntegerField()
    blob = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    bytes = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bundle", "ordinal"], name="export_part_unique")
        ]


class DraftSnapshot(models.Model):
    draft = models.ForeignKey(
        "records.Record", on_delete=models.PROTECT, related_name="frozen_reports"
    )
    snapshot = models.OneToOneField(
        "records.Record", on_delete=models.PROTECT, related_name="source_draft"
    )
    created_at = models.DateTimeField(auto_now_add=True)
