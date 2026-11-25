import hashlib

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import Invitation


def invitation_query(request):
    return Invitation.objects.filter(
        secret_hash=request.session.get("enrollment_invitation_hash", ""),
        consumed_at__isnull=True,
        expires_at__gt=timezone.now(),
    )


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InvitationAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return invitation_query(request).exists()

    @transaction.atomic
    def save_user(self, request, user, form, commit=True):
        invitation = invitation_query(request).select_for_update().first()
        if (
            invitation is None
            or form.cleaned_data.get("email", "").lower() != invitation.email.lower()
        ):
            raise ImmediateHttpResponse(
                JsonResponse({"code": "enrollment_unavailable"}, status=400)
            )
        user = super().save_user(request, user, form, commit=False)
        user.email = invitation.email.lower()
        user.role = invitation.role
        user.enrollment_complete = True
        user.save()
        invitation.account = user
        invitation.consumed_at = timezone.now()
        invitation.save(update_fields=["account", "consumed_at"])
        request.session.pop("enrollment_invitation_hash", None)
        return user

    def send_password_reset_mail(self, user, email, context):
        if (
            user.enrollment_complete
            and EmailAddress.objects.filter(user=user, email__iexact=email, verified=True).exists()
        ):
            return super().send_password_reset_mail(user, email, context)

    def clean_email(self, email):
        email = super().clean_email(email).lower()
        # Bind signup input before allauth creates the account, avoiding a 500 on mismatch.
        if self.request.path.endswith("/auth/signup"):
            invitation = invitation_query(self.request).first()
            if invitation is None or invitation.email.lower() != email:
                raise ValidationError("Enrollment is unavailable.")
        return email
