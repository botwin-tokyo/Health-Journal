import uuid

from django.db import models
from django.utils import timezone


class CacheEntry(models.Model):
    key = models.CharField(primary_key=True, max_length=255)
    value = models.JSONField()
    expires_at = models.DateTimeField(null=True, db_index=True)


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField(null=True)
    actor_type = models.CharField(max_length=12)
    action = models.CharField(max_length=40)
    target_id = models.UUIDField(null=True)
    outcome = models.CharField(max_length=10)
    request_id = models.UUIDField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)


class SecurityOutbox(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner_id = models.UUIDField()
    target_id = models.UUIDField()
    action = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True)
    remote_sequence = models.PositiveBigIntegerField(null=True)
    remote_hash = models.CharField(max_length=64, blank=True)


class OperationalControl(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    incident_locked = models.BooleanField(default=False)
    restored_candidate = models.BooleanField(default=False)


class BackupSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=16, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    manifest_snapshot = models.CharField(max_length=64, blank=True)
    manifest = models.JSONField(default=dict)
    error_code = models.CharField(max_length=40, blank=True)


class DeletionRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField()
    scope = models.CharField(max_length=16, default="account")
    accepted_at = models.DateTimeField(auto_now_add=True)
    purge_by = models.DateTimeField()
    purged_at = models.DateTimeField(null=True)
    backup_retention_days = models.PositiveSmallIntegerField(default=35)
