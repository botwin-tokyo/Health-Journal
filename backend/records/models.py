import uuid

from django.conf import settings
from django.db import models


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_epoch = models.PositiveBigIntegerField(default=0)


class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32)
    current = models.ForeignKey("Revision", null=True, on_delete=models.PROTECT, related_name="+")
    version = models.PositiveIntegerField(default=0)
    superseded_at = models.DateTimeField(null=True)
    deleted_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Revision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(Record, on_delete=models.PROTECT, related_name="revisions")
    version = models.PositiveIntegerField()
    blob = models.OneToOneField("artifacts.SecureRecord", on_delete=models.PROTECT)
    measured_start = models.DateTimeField(null=True, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["record", "version"], name="record_version_unique")
        ]


class Mutation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    route_digest = models.CharField(max_length=64)
    body_digest = models.CharField(max_length=100)
    record = models.ForeignKey(Record, on_delete=models.PROTECT)
    revision = models.ForeignKey(Revision, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "key", "route_digest"], name="mutation_key_unique"
            )
        ]


class Designation(models.Model):
    automatic = models.BooleanField(default=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    clinical_date = models.DateField()
    domain = models.CharField(max_length=16)
    slot = models.CharField(max_length=16, default="")
    record = models.ForeignKey(Record, null=True, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "clinical_date", "domain", "slot"],
                name="daily_designation_unique",
            )
        ]


class ActionReceipt(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    route_digest = models.CharField(max_length=64)
    body_digest = models.CharField(max_length=100)
    response = models.JSONField()  # Operation IDs/state only, never clinical response bodies.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "key", "route_digest"], name="action_receipt_unique"
            )
        ]


class RegistryDefinition(models.Model):
    key = models.CharField(primary_key=True, max_length=80)
    version = models.CharField(max_length=40)
    definition = models.JSONField()  # Public capability metadata only.
