"""Server-derived contexts and record-level policy, shared by selectors/envelopes.

RecordRef must be built from persisted metadata by a domain selector, never a
client request body. No clinical-record endpoint is exposed by this module.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from accounts.models import Account
from accounts.policy import eligible
from crypto.envelopes import Identity, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import CATEGORIES, SharingGrant


class AccessDenied(Exception):
    def __init__(self):
        super().__init__("Record unavailable")


@dataclass(frozen=True)
class RecordRef:
    identity: Identity
    category: str
    clinical_date: date
    visibility: str = "private"
    parent: "RecordRef | None" = field(default=None, repr=False)
    dependencies: tuple["RecordRef", ...] = field(default=(), repr=False)
    owner_only: bool = False
    parent_candidates: tuple["RecordRef", ...] = field(default=(), repr=False)
    audience_grant: uuid.UUID | None = None


class AuthorizationContext:
    def __init__(self, request):
        self.request = request

    def _principal(self):
        request = self.request
        if not request.user.is_authenticated:
            raise AccessDenied()
        # One fresh joined query validates account, verified email and live session.
        # This is not a permission cache: it runs before every protected unwrap.
        from accounts.adapter import token_hash
        from django.db.models import F

        if not request.session.session_key:
            raise AccessDenied()
        now = timezone.now()
        user = Account.objects.filter(
            pk=request.user.pk,
            is_active=True,
            enrollment_complete=True,
            emailaddress__verified=True,
            emailaddress__email__iexact=F("email"),
            sessionsecurity__pk=token_hash(request.session.session_key),
            sessionsecurity__security_epoch=F("security_epoch"),
            sessionsecurity__idle_expires_at__gt=now,
            sessionsecurity__absolute_expires_at__gt=now,
        ).first()
        if user is None:
            raise AccessDenied()
        request.user = user
        selected = request.session.get("active_grant_id")
        preview = request.GET.get("view_grant_id")
        if preview:
            if request.method != "GET" or user.role != "owner":
                raise AccessDenied()
            selected = preview
        return user, selected

    def current(self):
        user, selected = self._principal()
        grant = None
        if selected:
            try:
                selected = uuid.UUID(selected)
            except (ValueError, TypeError, AttributeError):
                raise AccessDenied() from None
            grant = (
                SharingGrant.objects.select_related("owner", "recipient")
                .filter(pk=selected)
                .first()
            )
            now = timezone.now()
            if (
                grant is None
                or grant.state != "active"
                or grant.revoked_at is not None
                or grant.approved_at is None
                or now < grant.not_before
                or now >= grant.expires_at
                or grant.expires_at > grant.approved_at + timedelta(days=180)
                or not eligible(grant.owner)
                or grant.owner.role != "owner"
                or not eligible(grant.recipient)
                or grant.recipient.role != "doctor"
            ):
                raise AccessDenied()
            if not (
                (user.role == "owner" and grant.owner_id == user.pk)
                or (user.role == "doctor" and grant.recipient_id == user.pk)
            ):
                raise AccessDenied()
            try:
                grant.clean()
            except (ValidationError, ValueError, TypeError):
                raise AccessDenied() from None
            owner = grant.owner
        elif user.role == "owner":
            owner = user
        else:
            owner = None
        return user, owner, grant

    def epoch(self):
        return self._epoch(self.current())

    @staticmethod
    def _epoch(principal):
        user, owner, grant = principal
        value = ":".join(
            [
                str(user.security_epoch),
                str(owner.pk) if owner else "",
                str(owner.sharing_epoch) if owner else "",
                str(grant.pk) if grant else "",
            ]
        )
        return salted_hmac("health03.permission-epoch", value).hexdigest()

    def require(self, record, action="read"):
        return self._require(record, action, self.current())

    def _require(self, record, action, principal):
        _, owner, grant = principal
        if owner is None or record.identity.owner_id != owner.pk:
            raise AccessDenied()
        if not self._allows(record, action, owner, grant, frozenset(), 0, [128]):
            raise AccessDenied()
        return True

    def _allows(self, record, action, owner, grant, seen, depth, budget):
        budget[0] -= 1
        if (
            budget[0] < 0
            or record.category not in CATEGORIES
            or (record.clinical_date is not None and type(record.clinical_date) is not date)
        ):
            return False
        try:
            record.identity.aad()
        except (IntegrityError, TypeError, AttributeError):
            return False
        identity = record.identity
        marker = (identity.object_id, identity.revision_id)
        if (
            marker in seen
            or depth > 16
            or len(record.dependencies) > 128
            or identity.owner_id != owner.pk
        ):
            return False
        seen = seen | {marker}
        if grant is None:
            allowed = action in {"read", "write", "download_report", "read_original_document"}
        else:
            if record.owner_only:
                return False
            if identity.kind in {"profile_revision", "source_identity"}:
                return False
            if action not in grant.actions or action == "write":
                return False
            if identity.kind == "report_snapshot":
                allowed = record.audience_grant == grant.pk and action in {
                    "read",
                    "download_report",
                }
            elif identity.kind == "lab_document":
                # Whole original-document consent is separate from structured result scope.
                allowed = (
                    action == "read_original_document"
                    and str(identity.object_id) in grant.whole_document_ids
                )
            else:
                allowed = (
                    record.category in grant.categories
                    and type(record.clinical_date) is date
                    and grant.starts_on <= record.clinical_date <= grant.ends_on
                )
                if record.category in {"journal", "questions"}:
                    selection = (
                        grant.selected_entry_ids
                        if record.category == "journal"
                        else grant.selected_question_ids
                    )
                    allowed = (
                        allowed
                        and record.visibility == "shared"
                        and str(identity.object_id) in selection
                    )
                if record.category == "labs" and grant.selected_result_ids is not None:
                    allowed = allowed and str(identity.object_id) in grant.selected_result_ids
                if identity.kind == "medication_event":
                    allowed = (
                        record.category == "journal"
                        and record.visibility == "shared"
                        and grant.starts_on <= record.clinical_date <= grant.ends_on
                        and "journal" in grant.categories
                        and str(identity.object_id) in grant.selected_medication_event_ids
                        and any(
                            self._allows(candidate, "read", owner, grant, seen, depth + 1, budget)
                            for candidate in ((record.parent,) if record.parent else ())
                            + record.parent_candidates
                        )
                    )
        if not allowed:
            return False
        return all(
            self._allows(
                dependency,
                "read_original_document" if dependency.identity.kind == "lab_document" else "read",
                owner,
                grant,
                seen,
                depth + 1,
                budget,
            )
            for dependency in record.dependencies
        )

    def envelope_authorizer(self, record, action="read", selected_epoch=None):
        selected_epoch = selected_epoch or self.epoch()

        def authorize(identity, requested_action):
            if identity != record.identity or requested_action != (
                "write" if action == "write" else "read"
            ):
                raise AccessDenied()
            principal = self.current()
            if self._epoch(principal) != selected_epoch:
                raise AccessDenied()
            return self._require(record, action, principal)

        return authorize

    def select(self, records, action="read"):
        if len(records) > 128:
            raise ValueError("Selection exceeds security page bound")
        # Evaluate the whole selection before returning anything for key-cache/unwrap work.
        for record in records:
            self.require(record, action)
        return tuple(records)


class JobAuthorizationContext(AuthorizationContext):
    """A job is bound to a still-live originating session, never just an account ID."""

    def __init__(self, actor_id, session_hash, grant_id):
        self.actor_id, self.session_hash, self.grant_id = actor_id, session_hash, grant_id

    def _principal(self):
        from accounts.models import SessionSecurity

        now = timezone.now()
        user = Account.objects.filter(pk=self.actor_id).first()
        if (
            user is None
            or not eligible(user)
            or not SessionSecurity.objects.filter(
                pk=self.session_hash,
                account=user,
                security_epoch=user.security_epoch,
                idle_expires_at__gt=now,
                absolute_expires_at__gt=now,
            ).exists()
        ):
            raise AccessDenied()
        return user, str(self.grant_id) if self.grant_id else None


class BoundGrantContext(AuthorizationContext):
    def __init__(self, base, grant_id):
        self.base, self.grant_id = base, str(grant_id)

    def _principal(self):
        user, selected = self.base._principal()
        if selected and str(selected) != self.grant_id:
            raise AccessDenied()
        if user.role == "doctor" and str(selected) != self.grant_id:
            raise AccessDenied()
        return user, self.grant_id


class AggregateAuthorizationContext(AuthorizationContext):
    """Internal recomputation only; never accepted from an HTTP request or grant."""

    def __init__(self, owner_id):
        self.owner_id = owner_id

    def _principal(self):
        from operations.models import OperationalControl

        user = Account.objects.filter(pk=self.owner_id, role="owner").first()
        if (
            user is None
            or not eligible(user)
            or OperationalControl.objects.filter(incident_locked=True).exists()
        ):
            raise AccessDenied()
        return user, None
