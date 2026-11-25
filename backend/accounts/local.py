"""Explicit loopback desktop access; through the local development or authenticated appliance proxy."""

from urllib.parse import urlsplit

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .adapter import token_hash
from .models import Account, SessionSecurity
from .policy import ABSOLUTE, IDLE


@require_POST
def enter(request):
    if (
        not settings.HEALTH03_LOCAL_DESKTOP
        or (settings.ENVIRONMENT != "development" and not getattr(request, "trusted_desktop", False))
        or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
        or request.headers.get("Origin") != settings.FRONTEND_ORIGIN
        or urlsplit(settings.FRONTEND_ORIGIN).hostname != "localhost"
        or request.get_host() != urlsplit(settings.API_ORIGIN).netloc
    ):
        return JsonResponse({"code": "not_found"}, status=404)
    owner = Account.objects.filter(role="owner").first()
    if owner is None:
        owner = Account.objects.create_user(
            "local-owner@health03.invalid", role="owner", enrollment_complete=True
        )
        EmailAddress.objects.create(user=owner, email=owner.email, verified=True, primary=True)
    if (
        owner.email != "local-owner@health03.invalid"
        or not owner.is_active
        or not owner.enrollment_complete
    ):
        return JsonResponse({"code": "local_context_unavailable"}, status=403)
    login(request, owner, backend="allauth.account.auth_backends.AuthenticationBackend")
    now = timezone.now()
    SessionSecurity.objects.update_or_create(
        pk=token_hash(request.session.session_key),
        defaults={
            "account": owner,
            "security_epoch": owner.security_epoch,
            "created_at": now,
            "last_user_activity_at": now,
            "idle_expires_at": now + IDLE,
            "absolute_expires_at": now + ABSOLUTE,
            "password_verified_at": now,
        },
    )
    return JsonResponse({"status": "local_context_ready"})
