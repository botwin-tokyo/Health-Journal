import uuid

from django.db import models
from django.utils import timezone


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32)
    reference = models.UUIDField()
    deduplication_key = models.CharField(max_length=128, unique=True)
    state = models.CharField(max_length=12, default="queued")
    available_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
