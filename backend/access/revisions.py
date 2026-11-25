from accounts.models import Account
from accounts.policy import fresh, session_state
from artifacts.models import DownloadTicket, SecurityJob
from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone
from records.actions import Command
from records.validation import DomainError, parse_json

from .models import GrantOffer, GrantRevision, SharingGrant

FIELDS = [
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
]


def scope(grant):
    return {
        field: getattr(grant, field).isoformat()
        if hasattr(getattr(grant, field), "isoformat")
        else getattr(grant, field)
        for field in FIELDS
    }


def record(grant):
    latest = GrantRevision.objects.filter(grant=grant).order_by("-version").first()
    GrantRevision.objects.create(
        grant=grant, version=latest.version + 1 if latest else 1, scope=scope(grant)
    )


def patch(request, grant_id):
    from datetime import date, datetime

    from .views import scope_etag

    command = Command(request)
    body = parse_json(request.body)
    if set(body) - set(FIELDS):
        raise DomainError("unknown_scope_field")

    def apply():
        grant = (
            SharingGrant.objects.select_for_update().filter(pk=grant_id, owner=request.user).first()
        )
        if not grant:
            raise DomainError("not_found", 404)
        if not request.headers.get("If-Match"):
            raise DomainError("precondition_required", 428)
        if request.headers["If-Match"] != scope_etag(grant):
            raise DomainError("revision_conflict", 412)
        if grant.state == "revoked" or grant.expires_at <= timezone.now():
            raise DomainError("new_grant_required", 409)
        before = scope(grant)
        for key, value in body.items():
            if key in {"starts_on", "ends_on"}:
                value = date.fromisoformat(value)
            if key == "expires_at":
                value = datetime.fromisoformat(value)
            setattr(grant, key, value)
        try:
            grant.full_clean()
        except ValidationError:
            raise DomainError("invalid_grant_scope") from None
        if grant.state == "active":
            if grant.recipient_email != before["recipient_email"]:
                raise DomainError("new_grant_required", 409)
            expansion = (
                grant.starts_on < date.fromisoformat(before["starts_on"])
                or grant.ends_on > date.fromisoformat(before["ends_on"])
                or grant.expires_at > datetime.fromisoformat(before["expires_at"])
            )
            for field in [
                "categories",
                "actions",
                "selected_entry_ids",
                "selected_question_ids",
                "selected_medication_event_ids",
                "whole_document_ids",
            ]:
                expansion = expansion or not set(getattr(grant, field)) <= set(before[field])
            old, new = before["selected_result_ids"], grant.selected_result_ids
            expansion = expansion or (old is not None and (new is None or not set(new) <= set(old)))
            if expansion:
                raise DomainError("new_grant_required", 409)
        elif GrantOffer.objects.filter(grant=grant).exists():
            if not fresh(session_state(request)):
                raise DomainError("reauthentication_required", 403)
            from accounts.models import Invitation

            Invitation.objects.filter(
                secret_hash__in=GrantOffer.objects.filter(grant=grant).values("token_hash")
            ).delete()
            GrantOffer.objects.filter(grant=grant).delete()
        record(grant)
        grant.save()
        Account.objects.filter(pk=grant.owner_id).update(sharing_epoch=F("sharing_epoch") + 1)
        DownloadTicket.objects.filter(grant_id=grant.pk).delete()
        SecurityJob.objects.filter(grant_id=grant.pk).update(
            state="cancelled", error_code="permission_changed"
        )
        # A retained backup must not re-open the broader grant; restore already leaves all grants inactive.
        from operations.ledger import enqueue

        if grant.state == "active":
            enqueue(grant.owner_id, "grant_revoked", grant.pk)
        return {
            "id": str(grant.pk),
            "status": "scope_updated",
            "context_reset_required": True,
            "next_permission_epoch": command.context.epoch(),
        }

    return command.run(apply)
