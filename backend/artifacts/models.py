import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SecureRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_id = models.UUIDField(default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    category = models.CharField(max_length=24)
    clinical_date = models.DateField(null=True)
    owner_only = models.BooleanField(default=False)
    audience_grant = models.UUIDField(null=True)
    mime_type = models.CharField(max_length=64, default="application/json")
    visibility = models.CharField(max_length=10, default="private")
    schema_version = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    dependencies = models.ManyToManyField("self", symmetrical=False, related_name="derived_records")
    blob_name = models.CharField(max_length=64, unique=True)
    ciphertext_sha256 = models.CharField(max_length=64)
    ciphertext_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True)
    purge_after = models.DateTimeField(null=True)
    purged_at = models.DateTimeField(null=True)


class SecurityJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="security_jobs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_jobs"
    )
    purpose = models.CharField(max_length=24)
    session_hash = models.CharField(max_length=64)
    grant_id = models.UUIDField(null=True)
    permission_epoch = models.CharField(max_length=64)
    input_record = models.ForeignKey(
        SecureRecord, on_delete=models.PROTECT, related_name="input_jobs"
    )
    output_record = models.ForeignKey(
        SecureRecord, null=True, on_delete=models.PROTECT, related_name="output_jobs"
    )
    state = models.CharField(max_length=12, default="queued")
    error_code = models.CharField(max_length=40, blank=True)
    lease_id = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    heartbeat_at = models.DateTimeField(null=True)
    available_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(state="running", purpose="render_report"),
                name="one_running_owner_export",
            )
        ]


class DownloadTicket(models.Model):
    digest = models.CharField(primary_key=True, max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    record = models.ForeignKey(SecureRecord, on_delete=models.CASCADE)
    session_hash = models.CharField(max_length=64)
    permission_epoch = models.CharField(max_length=64)
    grant_id = models.UUIDField(null=True)
    action = models.CharField(max_length=32)
    deadline = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
