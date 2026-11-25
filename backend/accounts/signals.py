import uuid
from datetime import datetime
from datetime import timezone as dt_timezone

from allauth.account import signals
from allauth.account.authentication import get_authentication_records
from django.contrib.auth.signals import user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from .adapter import token_hash
from .models import Account, SessionSecurity
from .policy import ABSOLUTE, IDLE, eligible, session_state


@receiver(signals.user_logged_in)
def establish_password_session(sender, request, user, **kwargs):
    records = [
        r for r in get_authentication_records(request, user) if r.get("method") == "password"
    ]
    if not eligible(user) or not records:
        return
    now = timezone.now()
    proof_at = datetime.fromtimestamp(records[-1]["at"], tz=dt_timezone.utc)
    if now - proof_at > IDLE:
        return
    if not request.session.session_key:
        request.session.save()
    from operations.audit import emit

    emit("login_success", actor=user)
    SessionSecurity.objects.update_or_create(
        pk=token_hash(request.session.session_key),
        defaults={
            "account": user,
            "security_epoch": user.security_epoch,
            "created_at": now,
            "last_user_activity_at": now,
            "idle_expires_at": now + IDLE,
            "absolute_expires_at": now + ABSOLUTE,
            "password_verified_at": proof_at,
        },
    )


@receiver(signals.authentication_step_completed)
def password_step_up(sender, request, user, method, **kwargs):
    if method != "password" or not request.user.is_authenticated or request.user.pk != user.pk:
        return
    state = session_state(request)
    if state:
        state.password_verified_at = timezone.now()
        state.save(update_fields=["password_verified_at"])


@receiver(signals.password_reset)
@receiver(signals.password_changed)
@receiver(signals.password_set)
@receiver(signals.email_changed)
def revoke_credentials(sender, request, user, **kwargs):
    Account.objects.filter(pk=user.pk).update(security_epoch=uuid.uuid4())
    SessionSecurity.objects.filter(account=user).delete()
    from uploader.policy import revoke_account_families

    revoke_account_families(user)
    from artifacts.models import DownloadTicket
    from operations.audit import emit

    DownloadTicket.objects.filter(actor=user).delete()
    emit("credential_change", actor=user)
    request.revoke_browser_session = True


@receiver(user_logged_out)
def invalidate_logged_out_session(sender, request, **kwargs):
    if request.session.session_key:
        SessionSecurity.objects.filter(pk=token_hash(request.session.session_key)).delete()


@receiver(user_login_failed)
def audit_failed_login(sender, request=None, **kwargs):
    from operations.audit import emit

    emit("login_denied", outcome="denied")
