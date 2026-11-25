"""Atomic metadata-only command receipts; callers prepare ciphertext before run()."""

import hashlib
import uuid

from crypto.envelopes import TransitKMS
from django.db import transaction

from .models import ActionReceipt, Patient
from .service import owner_context
from .validation import DomainError


class Command:
    def __init__(self, request, owner_only=True):
        self.request = request
        self.owner_only = owner_only
        if owner_only:
            self.context, self.patient = owner_context(request)
        else:
            from access.policy import AccessDenied, AuthorizationContext

            self.context = AuthorizationContext(request)
            _, owner, _ = self.context.current()
            if owner is None:
                raise AccessDenied()
            self.patient = Patient.objects.get(owner=owner)
        self._initialize()

    def _reauthorize(self):
        if self.owner_only:
            owner_context(self.request)
        else:
            self.context.current()

    def _initialize(self):
        request = self.request
        try:
            self.key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except (ValueError, TypeError):
            raise DomainError("idempotency_key_required", 400) from None
        self.route = hashlib.sha256((request.method + request.path).encode()).hexdigest()
        self.digest = TransitKMS().identity_digest(
            self.patient.owner_id, "action", hashlib.sha256(request.body).hexdigest(), self.route, 1
        )

    def previous(self):
        self._reauthorize()
        row = ActionReceipt.objects.filter(
            actor=self.request.user,
            key=self.key,
            route_digest=self.route
        ).first()
        if row and row.body_digest != self.digest:
            raise DomainError("idempotency_conflict", 409)
        if row:
            response = dict(row.response)
            if response.get("context_reset_required"):
                response["next_permission_epoch"] = self.context.epoch()
            return response
        return None

    def run(self, commit, authorize=None):
        with transaction.atomic():
            Patient.objects.select_for_update().get(pk=self.patient.pk)
            self._reauthorize()
            if authorize:
                authorize()
            previous = self.previous()
            if previous is not None:
                return previous
            result = commit()
            ActionReceipt.objects.create(
                actor=self.request.user,
                key=self.key,
                route_digest=self.route,
                body_digest=self.digest,
                response=result,
            )
        return result
