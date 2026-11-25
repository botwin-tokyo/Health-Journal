import uuid

from .models import AuditEvent

ACTIONS = {
    "record_saved",
    "lab_published",
    "login_success",
    "login_denied",
    "logout",
    "enrollment",
    "recovery",
    "credential_change",
    "device_authorized",
    "device_revoked",
    "grant_approved",
    "grant_revoked",
    "scope_denied",
    "scoped_view",
    "export_requested",
    "document_delivered",
    "record_deleted",
    "record_private",
    "account_closed",
    "integrity_failure",
    "operator_recovery",
    "incident_lock",
    "backup_complete",
    "backup_failed",
}


def emit(action, actor=None, target=None, outcome="success", request_id=None):
    if action not in ACTIONS or outcome not in {"success", "denied", "failed", "pending"}:
        raise ValueError("Invalid audit metadata")
    if target is not None:
        target = uuid.UUID(str(target))
    return AuditEvent.objects.create(
        action=action,
        actor_id=actor.pk if actor else None,
        actor_type=actor.role if actor else "system",
        target_id=target,
        outcome=outcome,
        request_id=uuid.UUID(str(request_id)) if request_id else uuid.uuid4(),
    )
