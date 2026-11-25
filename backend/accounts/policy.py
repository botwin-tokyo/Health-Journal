from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.utils import timezone

from .adapter import token_hash
from .models import SessionSecurity

IDLE = timedelta(minutes=15)
ABSOLUTE = timedelta(hours=12)
FRESH = timedelta(minutes=5)


def eligible(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.enrollment_complete
        and EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()
    )


def session_state(request):
    if not eligible(request.user) or not request.session.session_key:
        return None
    state = SessionSecurity.objects.filter(
        pk=token_hash(request.session.session_key),
        account=request.user,
        security_epoch=request.user.security_epoch,
    ).first()
    now = timezone.now()
    if state is None or now >= state.idle_expires_at or now >= state.absolute_expires_at:
        return None
    return state


def fresh(state):
    if (
        settings.HEALTH03_LOCAL_DESKTOP
        and state is not None
        and state.account.email == "local-owner@health03.invalid"
    ):
        return True
    return state is not None and timezone.now() < state.password_verified_at + FRESH
