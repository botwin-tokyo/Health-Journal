import uuid

from django.conf import settings
from django.db import models


class DeviceRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    active_family = models.UUIDField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TokenFamily(models.Model):
    id = models.UUIDField(primary_key=True)
    device = models.ForeignKey(DeviceRegistration, on_delete=models.CASCADE)
    security_epoch = models.UUIDField()
    family_authorized_at = models.DateTimeField()
    absolute_expires_at = models.DateTimeField()
    last_successful_refresh_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)


class CodeBinding(models.Model):
    grant = models.OneToOneField(
        "oauth2_provider.Grant", primary_key=True, on_delete=models.CASCADE
    )
    device = models.ForeignKey(DeviceRegistration, on_delete=models.CASCADE)
    security_epoch = models.UUIDField()


class AccessBinding(models.Model):
    token = models.OneToOneField(
        "oauth2_provider.AccessToken", primary_key=True, on_delete=models.CASCADE
    )
    device = models.ForeignKey(DeviceRegistration, on_delete=models.CASCADE)
    family = models.ForeignKey(TokenFamily, on_delete=models.CASCADE)


class AuthorizationContinuation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    browser_secret_hash = models.CharField(max_length=64)
    parameters = models.JSONField()
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class DeviceAPIKey(models.Model):
    """Persistent uploader credential. Only its SHA-256 digest is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(DeviceRegistration, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)
