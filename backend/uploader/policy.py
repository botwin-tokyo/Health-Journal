from datetime import timedelta

from accounts.policy import eligible
from django.utils import timezone
from oauth2_provider.models import RefreshToken

from .models import TokenFamily

NATIVE_LOCK = 3103003
IDLE = timedelta(days=30)
ABSOLUTE = timedelta(days=180)


def family_active(family):
    now = timezone.now()
    owner = family.device.owner
    return (
        family.revoked_at is None
        and family.device.revoked_at is None
        and family.device.active_family == family.pk
        and eligible(owner)
        and owner.role == "owner"
        and owner.security_epoch == family.security_epoch
        and now < family.absolute_expires_at
        and now < family.last_successful_refresh_at + IDLE
    )


def revoke_family(family_id):
    RefreshToken.revoke_family(family_id)
    TokenFamily.objects.filter(pk=family_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def revoke_account_families(account):
    for family_id in TokenFamily.objects.filter(
        device__owner=account, revoked_at__isnull=True
    ).values_list("pk", flat=True):
        revoke_family(family_id)
