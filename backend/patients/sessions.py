from access.policy import AccessDenied
from accounts.models import SessionSecurity
from accounts.policy import session_state
from artifacts.models import DownloadTicket, SecurityJob
from django.utils import timezone
from records.actions import Command
from records.http import endpoint
from records.service import owner_context
from records.validation import DomainError, parse_json
from reports.models import ExportBundle


@endpoint({"GET", "POST"})
def sessions(request, session_id=None):
    owner_context(request)
    current = session_state(request)
    if current is None:
        raise AccessDenied()
    if request.method == "GET":
        return {
            "items": [
                {
                    "id": row.pk,
                    "current": row.pk == current.pk,
                    "created_at": row.created_at,
                    "last_activity_at": row.last_user_activity_at,
                    "expires_at": min(row.idle_expires_at, row.absolute_expires_at),
                }
                for row in SessionSecurity.objects.filter(
                    account=request.user,
                    idle_expires_at__gt=timezone.now(),
                    absolute_expires_at__gt=timezone.now(),
                ).order_by("-created_at")[:100]
            ]
        }
    command = Command(request)
    body = {"session_id": session_id} if session_id else parse_json(request.body)
    if set(body) != {"session_id"} or not isinstance(body["session_id"], str):
        raise DomainError("invalid_session_selection")
    identifier = body["session_id"]

    def commit():
        SessionSecurity.objects.filter(pk=identifier, account=request.user).delete()
        DownloadTicket.objects.filter(actor=request.user, session_hash=identifier).delete()
        SecurityJob.objects.filter(actor=request.user, session_hash=identifier).update(
            state="cancelled", error_code="session_revoked"
        )
        ExportBundle.objects.filter(actor=request.user, session_hash=identifier).update(
            state="revoked", error_code="session_revoked"
        )
        return {"status": "revoked", "current_session_revoked": identifier == current.pk}

    return command.run(commit)
