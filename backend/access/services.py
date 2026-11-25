from datetime import timedelta

from accounts.models import Account
from accounts.policy import eligible, fresh, session_state
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import SharingGrant
from .policy import AccessDenied


@transaction.atomic
def approve_grant(request, grant_id):
    state = session_state(request)
    if state is None or request.user.role != "owner" or not fresh(state):
        raise AccessDenied()
    grant = SharingGrant.objects.select_for_update().filter(pk=grant_id, owner=request.user).first()
    if (
        grant is None
        or grant.state != "draft"
        or not eligible(grant.recipient)
        or grant.recipient.role != "doctor"
        or not grant.categories
        or not grant.actions
    ):
        raise AccessDenied()
    now = timezone.now()
    if not now < grant.expires_at <= now + timedelta(days=180):
        raise AccessDenied()
    grant.full_clean()
    grant.state, grant.approved_at = "active", now
    grant.save(update_fields=["state", "approved_at"])
    Account.objects.filter(pk=grant.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
    return grant


@transaction.atomic
def revoke_grant(request, grant_id):
    if session_state(request) is None or request.user.role != "owner":
        raise AccessDenied()
    grant = SharingGrant.objects.select_for_update().filter(pk=grant_id, owner=request.user).first()
    if grant is None:
        raise AccessDenied()
    grant.state, grant.revoked_at = "revoked", timezone.now()
    grant.save(update_fields=["state", "revoked_at"])
    Account.objects.filter(pk=grant.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
    from artifacts.models import DownloadTicket, SecurityJob
    from operations import audit, ledger

    SecurityJob.objects.filter(grant_id=grant.pk).update(
        state="cancelled", error_code="permission_changed"
    )
    DownloadTicket.objects.filter(grant_id=grant.pk).delete()
    ledger.enqueue(grant.owner_id, "grant_revoked", grant.pk)
    audit.emit("grant_revoked", request.user, grant.pk)
