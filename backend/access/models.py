import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

CATEGORIES = {"body", "breathing", "sleep_activity", "labs", "journal", "questions"}
ACTIONS = {"read", "download_report", "read_original_document"}


def default_expiry():
    return timezone.now() + timedelta(days=30)


class SharingGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issued_grants"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_grants",
        null=True,
        blank=True,
    )
    recipient_email = models.EmailField(blank=True)
    state = models.CharField(
        max_length=10,
        default="draft",
        choices=[("draft", "Draft"), ("active", "Active"), ("revoked", "Revoked")],
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    not_before = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_expiry)
    approved_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    categories = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    selected_entry_ids = models.JSONField(default=list, blank=True)
    selected_question_ids = models.JSONField(default=list, blank=True)
    selected_medication_event_ids = models.JSONField(default=list, blank=True)
    selected_result_ids = models.JSONField(null=True, default=None, blank=True)
    whole_document_ids = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="grant_finite_date_order",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("not_before")), name="grant_expiry_order"
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=["draft", "active", "revoked"]),
                name="grant_known_state",
            ),
        ]

    def clean(self):
        super().clean()
        if not isinstance(self.categories, list) or not set(self.categories) <= CATEGORIES:
            raise ValidationError("Invalid grant categories")
        if not isinstance(self.actions, list) or not set(self.actions) <= ACTIONS:
            raise ValidationError("Invalid grant actions")
        for field in (
            "selected_entry_ids",
            "selected_question_ids",
            "selected_medication_event_ids",
            "selected_result_ids",
            "whole_document_ids",
        ):
            values = getattr(self, field)
            if values is None and field == "selected_result_ids":
                continue
            if not isinstance(values, list) or len(values) > 1000:
                raise ValidationError("Invalid grant selection")
            try:
                if any(str(uuid.UUID(value)) != value for value in values):
                    raise ValueError
            except (ValueError, AttributeError, TypeError):
                raise ValidationError("Invalid grant selection") from None


class GrantOffer(models.Model):
    grant = models.OneToOneField(SharingGrant, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True)
    scope_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)


class GrantRevision(models.Model):
    grant = models.ForeignKey(SharingGrant, on_delete=models.PROTECT, related_name="history")
    version = models.PositiveIntegerField()
    scope = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["grant", "version"], name="grant_revision_unique")
        ]
