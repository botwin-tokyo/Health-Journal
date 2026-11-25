from datetime import date

from accounts.models import Account
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.db import transaction
from records.http import endpoint
from records.service import owner_context
from records.validation import DomainError, parse_json

from access.policy import AccessDenied

from .models import SharingGrant
from .services import revoke_grant


@endpoint({"GET", "POST", "PATCH"})
def grants(request, grant_id=None):
    if request.method == "PATCH":
        from .revisions import patch

        return patch(request, grant_id)
    if request.method == "GET":
        query = (
            SharingGrant.objects.filter(owner=request.user)
            if request.user.role == "owner"
            else SharingGrant.objects.filter(recipient=request.user)
        )
        if grant_id:
            query = query.filter(pk=grant_id)
        from django.utils import timezone

        from .models import GrantOffer
        from .revisions import scope

        items = []
        for grant in query.order_by("id")[:100]:
            state = grant.state
            if state != "revoked" and grant.expires_at <= timezone.now():
                state = "expired"
            elif state == "draft" and GrantOffer.objects.filter(grant=grant).exists():
                state = "pending"
            items.append(
                {"id": str(grant.pk), "state": state, "etag": scope_etag(grant), **scope(grant)}
            )
        return {"items": items}
    owner_context(request)
    body = parse_json(request.body)
    required = {
        "recipient_email",
        "from",
        "to",
        "categories",
        "actions",
        "record_allowlists",
        "document_ids",
    }
    if set(body) != required:
        raise DomainError("invalid_grant_scope")
    lists = body["record_allowlists"]
    if not isinstance(lists, dict) or set(lists) != {
        "journal",
        "questions",
        "labs",
        "medication_events",
    }:
        raise DomainError("explicit_allowlists_required")
    recipient = Account.objects.filter(
        email__iexact=body["recipient_email"],
        role="doctor",
        enrollment_complete=True,
        is_active=True,
    ).first()
    if recipient and not EmailAddress.objects.filter(user=recipient, verified=True).exists():
        raise DomainError("recipient_enrollment_required", 409)
    try:
        grant = SharingGrant(
            owner=request.user,
            recipient=recipient,
            recipient_email=body["recipient_email"].lower(),
            starts_on=date.fromisoformat(body["from"]),
            ends_on=date.fromisoformat(body["to"]),
            categories=body["categories"],
            actions=body["actions"],
            selected_entry_ids=lists["journal"],
            selected_question_ids=lists["questions"],
            selected_result_ids=lists["labs"],
            selected_medication_event_ids=lists["medication_events"],
            whole_document_ids=body["document_ids"],
        )
        grant.full_clean()
    except (ValueError, TypeError, ValidationError):
        raise DomainError("invalid_grant_scope") from None
    from records.actions import Command

    from .revisions import record

    command = Command(request)

    def commit():
        grant.save()
        record(grant)
        return {
            "id": str(grant.pk),
            "state": "draft",
            "invitation_status": "not_sent",
            "etag": scope_etag(grant),
        }

    return command.run(commit)


@endpoint({"POST"})
def revoke(request, grant_id):
    with transaction.atomic():
        revoke_grant(request, grant_id)
    from access.policy import AuthorizationContext

    return {
        "status": "revoked",
        "context_reset_required": True,
        "next_permission_epoch": AuthorizationContext(request).epoch(),
    }


def scope_etag(grant):
    import hashlib
    import json

    values = {
        key: str(getattr(grant, key))
        for key in [
            "id",
            "recipient_email",
            "starts_on",
            "ends_on",
            "expires_at",
            "categories",
            "actions",
            "selected_entry_ids",
            "selected_question_ids",
            "selected_medication_event_ids",
            "selected_result_ids",
            "whole_document_ids",
            "state",
        ]
    }
    return '"' + hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest() + '"'


@endpoint({"POST"})
def invite(request, grant_id):
    import secrets
    from datetime import timedelta

    from accounts.adapter import token_hash
    from accounts.models import Invitation
    from accounts.policy import fresh, session_state
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    from .models import GrantOffer

    owner_context(request)
    if not fresh(session_state(request)):
        raise DomainError("reauthentication_required", 403)
    from records.actions import Command

    command = Command(request)

    def commit():
        grant = (
            SharingGrant.objects.select_for_update()
            .filter(pk=grant_id, owner=request.user, state="draft")
            .first()
        )
        if not grant:
            raise AccessDenied()
        if request.headers.get("If-Match") != scope_etag(grant):
            raise DomainError("revision_conflict", 412)
        if not grant.categories or not grant.actions:
            raise DomainError("empty_grant_scope")
        now = timezone.now()
        if not now < grant.expires_at <= now + timedelta(days=180):
            raise DomainError("invalid_grant_expiry")
        if GrantOffer.objects.filter(grant=grant).exists():
            raise DomainError("invitation_already_issued", 409)
        secret = secrets.token_urlsafe(32)
        digest = token_hash(secret)
        GrantOffer.objects.create(
            grant=grant,
            token_hash=digest,
            scope_hash=scope_etag(grant).strip('"'),
            expires_at=now + timedelta(hours=72),
        )
        if not grant.recipient_id:
            Invitation.objects.create(
                email=grant.recipient_email,
                role="doctor",
                secret_hash=digest,
                expires_at=now + timedelta(hours=72),
            )
        link = settings.FRONTEND_ORIGIN + "/invite#token=" + secret
        transaction.on_commit(
            lambda: send_mail(
                "Your private health journal invitation",
                "Open your invitation: " + link,
                settings.DEFAULT_FROM_EMAIL,
                [grant.recipient_email],
                fail_silently=False,
            )
        )
        return {"id": str(grant.pk), "status": "invited"}

    return command.run(commit)


@endpoint({"POST"})
def accept(request):
    from accounts.adapter import token_hash
    from accounts.policy import eligible
    from django.db.models import F
    from django.utils import timezone

    from .models import GrantOffer

    body = parse_json(request.body)
    token = body.get("token")
    if (
        not isinstance(token, str)
        or len(token) > 128
        or request.user.role != "doctor"
        or not eligible(request.user)
    ):
        raise AccessDenied()
    with transaction.atomic():
        offer = (
            GrantOffer.objects.select_for_update()
            .filter(
                token_hash=token_hash(token),
                accepted_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not offer:
            raise AccessDenied()
        grant = SharingGrant.objects.select_for_update().get(pk=offer.grant_id)
        if (
            grant.state != "draft"
            or scope_etag(grant).strip('"') != offer.scope_hash
            or grant.expires_at <= timezone.now()
        ):
            raise AccessDenied()
        if not EmailAddress.objects.filter(
            user=request.user, email__iexact=grant.recipient_email, verified=True
        ).exists():
            raise AccessDenied()
        grant.recipient = request.user
        grant.state = "active"
        grant.approved_at = timezone.now()
        grant.save()
        offer.accepted_at = timezone.now()
        offer.save(update_fields=["accepted_at"])
        Account.objects.filter(pk=grant.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
    return {"status": "accepted", "grant_id": str(grant.pk)}
