import secrets
from datetime import timedelta

from access.policy import AccessDenied, AuthorizationContext
from accounts.adapter import token_hash
from accounts.policy import fresh, session_state
from django.db import transaction
from django.utils import timezone

from .models import DownloadTicket
from .selectors import select
from .store import read


def issue(request, record_id, action):
    state = session_state(request)
    if not fresh(state) or action not in {"download_report", "read_original_document"}:
        raise AccessDenied()
    context = AuthorizationContext(request)
    record, _, _ = select(context, record_id, action)
    if action == "download_report" and record.created_at + timedelta(hours=24) <= timezone.now():
        raise AccessDenied()
    secret = secrets.token_urlsafe(32)
    DownloadTicket.objects.create(
        digest=token_hash(secret),
        actor=request.user,
        record=record,
        session_hash=state.pk,
        permission_epoch=context.epoch(),
        grant_id=request.session.get("active_grant_id"),
        action=action,
        deadline=timezone.now() + timedelta(seconds=60),
    )
    return secret


@transaction.atomic
def consume(request, record_id, secret):
    state = session_state(request)
    if state is None or not isinstance(secret, str) or not 32 <= len(secret) <= 128:
        raise AccessDenied()
    ticket = (
        DownloadTicket.objects.select_for_update()
        .filter(
            pk=token_hash(secret),
            actor=request.user,
            record_id=record_id,
            session_hash=state.pk,
            consumed_at__isnull=True,
            deadline__gt=timezone.now(),
        )
        .first()
    )
    context = AuthorizationContext(request)
    if ticket is None or ticket.permission_epoch != context.epoch():
        raise AccessDenied()
    record, metadata, authorize = select(context, record_id, ticket.action)
    if (
        ticket.action == "download_report"
        and record.created_at + timedelta(hours=24) <= timezone.now()
    ):
        raise AccessDenied()
    ticket.consumed_at = timezone.now()
    ticket.save(update_fields=["consumed_at"])
    # Commit consumption before decryption/transfer; a failed transfer needs a new ticket.
    return record, metadata, authorize, ticket.permission_epoch, ticket.action


def content(request, record_id, secret):
    record, metadata, authorize, epoch, action = consume(request, record_id, secret)
    payload = read(record, metadata.identity, authorize)
    context = AuthorizationContext(request)
    if context.epoch() != epoch:
        raise AccessDenied()
    select(context, record_id, action)

    def chunks():
        for start in range(0, len(payload), 64 * 1024):
            try:
                if context.epoch() != epoch:
                    return
                select(context, record_id, action)
            except AccessDenied:
                return
            yield payload[start : start + 64 * 1024]

    return chunks()
