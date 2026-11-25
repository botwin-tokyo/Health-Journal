import uuid

from django.db import models


class SourceConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey("uploader.DeviceRegistration", on_delete=models.PROTECT)
    namespace = models.UUIDField(unique=True)
    disabled_at = models.DateTimeField(null=True)


class IngestBatch(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    source = models.ForeignKey(SourceConnection, on_delete=models.PROTECT)
    body_digest = models.CharField(max_length=100)
    evidence = models.ForeignKey("artifacts.SecureRecord", on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default="received")
    item_count = models.PositiveIntegerField()
    received_at = models.DateTimeField(auto_now_add=True)


class ItemReceipt(models.Model):
    disposition = models.CharField(max_length=16, default="clinical")
    batch = models.ForeignKey(IngestBatch, on_delete=models.PROTECT, related_name="receipts")
    ordinal = models.PositiveIntegerField()
    outcome = models.CharField(max_length=24)
    reason = models.CharField(max_length=40)
    record_id = models.UUIDField(null=True)
    revision_id = models.UUIDField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["batch", "ordinal"], name="batch_ordinal_unique")
        ]


class SourceTombstone(models.Model):
    source = models.ForeignKey(SourceConnection, on_delete=models.PROTECT)
    identity_digest = models.CharField(max_length=100)
    lookup_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "identity_digest", "lookup_version"],
                name="tombstone_identity_unique",
            )
        ]


class SyncRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey("uploader.DeviceRegistration", on_delete=models.PROTECT)
    state = models.CharField(max_length=24, default="queued")
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SourceIdentity(models.Model):
    source = models.ForeignKey(SourceConnection, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    digest = models.CharField(max_length=100)
    lookup_version = models.PositiveIntegerField(default=1)
    record = models.OneToOneField("records.Record", on_delete=models.PROTECT)
    highest_revision = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "kind", "digest", "lookup_version"], name="source_identity_unique"
            )
        ]


class SourceVersion(models.Model):
    disposition = models.CharField(max_length=16, default="clinical")
    identity = models.ForeignKey(SourceIdentity, on_delete=models.PROTECT)
    source_revision = models.PositiveBigIntegerField()
    payload_digest = models.CharField(max_length=100)
    revision = models.ForeignKey("records.Revision", null=True, on_delete=models.PROTECT)
    outcome = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "source_revision"], name="source_version_unique"
            )
        ]


class SourceAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(SourceConnection, on_delete=models.PROTECT)
    intent_digest = models.CharField(max_length=100)
    content_digest = models.CharField(max_length=100)
    evidence = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "intent_digest", "content_digest"], name="source_asset_unique"
            )
        ]


class SourceLookup(models.Model):
    """Dual keyed indexes; the immutable identity and its evidence do not move."""

    identity = models.ForeignKey(SourceIdentity, on_delete=models.PROTECT, related_name="lookups")
    source = models.ForeignKey(SourceConnection, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    lookup_version = models.PositiveIntegerField()
    digest = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "kind", "lookup_version", "digest"], name="source_lookup_unique"
            ),
            models.UniqueConstraint(
                fields=["identity", "lookup_version"], name="identity_lookup_version_unique"
            ),
        ]
