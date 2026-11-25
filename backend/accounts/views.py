import json

from access.policy import AccessDenied, AuthorizationContext
from allauth.core import ratelimit
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .adapter import token_hash
from .models import Invitation, SessionSecurity
from .policy import IDLE


def csrf_failure(request, reason=""):
    response = JsonResponse({"code": "csrf_failed"}, status=403)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def bootstrap(request):
    return JsonResponse(
        {"csrf_token": get_token(request), "login_method": "password", "signup": "invitation_only"}
    )


@require_POST
def invitation(request):
    if not ratelimit.consume(request, action="enrollment"):
        return JsonResponse({"code": "rate_limited"}, status=429)
    try:
        token = json.loads(request.body).get("token", "")
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise ValueError
    except (ValueError, AttributeError, UnicodeDecodeError):
        return JsonResponse({"code": "enrollment_unavailable"}, status=400)
    digest = token_hash(token)
    valid = Invitation.objects.filter(
        secret_hash=digest, consumed_at__isnull=True, expires_at__gt=timezone.now()
    ).exists()
    if not valid:
        return JsonResponse({"code": "enrollment_unavailable"}, status=400)
    request.session.cycle_key()
    request.session["enrollment_invitation_hash"] = digest
    return JsonResponse({"status": "enrollment_available"})


@require_GET
def session(request):
    user, state = request.user, request.security_state
    context = AuthorizationContext(request)
    try:
        _, owner, grant = context.current()
        epoch = context.epoch()
    except AccessDenied:
        return JsonResponse({"code": "context_unavailable"}, status=403)
    latest_day = None
    if owner and not grant:
        from django.db.models import Max
        from records.models import Record

        latest_day = Record.objects.filter(
            patient__owner=owner,
            deleted_at__isnull=True,
            superseded_at__isnull=True,
            kind__in=[
                "weight",
                "pulmonary",
                "sleep",
                "workout",
                "lab",
                "journal",
                "question",
                "medication",
            ],
        ).aggregate(latest=Max("current__blob__clinical_date"))["latest"]
    return JsonResponse(
        {
            "latest_clinical_date": latest_day.isoformat() if latest_day else None,
            "account_id": str(user.pk),
            "role": user.role,
            "context": {
                "owner_id": str(owner.pk) if owner else None,
                "grant_id": str(grant.pk) if grant else None,
                "view_mode": ("owner_preview" if user.role == "owner" else "doctor")
                if grant
                else ("owner" if owner else "no_grant"),
            },
            "capabilities": (
                ["read", "write", "manage_sharing", "export"]
                if user.role == "owner" and not grant
                else list(grant.actions)
                if grant
                else []
            ),
            "server_time": timezone.now().isoformat(),
            "local_desktop": settings.HEALTH03_LOCAL_DESKTOP,
            "sample_data": user.email.endswith("@example.invalid"),
            "upload_limits": {"pdf_bytes": 26214400, "csv_bytes": 5242880, "pdf_pages": 100},
            "permission_epoch": epoch,
            "idle_expires_at": state.idle_expires_at.isoformat(),
            "absolute_expires_at": state.absolute_expires_at.isoformat(),
            "enrollment_state": "complete",
            "csrf_token": get_token(request),
            "preferences": {},
            "operational_summary": {"mode": "synthetic_development"},
            "auth_actions": [
                {
                    "rel": "reauthenticate",
                    "label": "Verify password",
                    "href": settings.API_ORIGIN + "/_allauth/browser/v1/auth/reauthenticate",
                    "method": "POST",
                },
                {
                    "rel": "logout",
                    "label": "Sign out",
                    "href": settings.API_ORIGIN + "/_allauth/browser/v1/auth/session",
                    "method": "DELETE",
                },
            ],
        }
    )


@require_POST
@transaction.atomic
def activity(request):
    state = SessionSecurity.objects.select_for_update().get(pk=request.security_state.pk)
    now = timezone.now()
    if now >= state.idle_expires_at or now >= state.absolute_expires_at:
        request.session.flush()
        return JsonResponse({"code": "authentication_required"}, status=401)
    state.last_user_activity_at = now
    state.idle_expires_at = min(now + IDLE, state.absolute_expires_at)
    state.save(update_fields=["last_user_activity_at", "idle_expires_at"])
    return JsonResponse({"idle_expires_at": state.idle_expires_at.isoformat()})


@require_GET
def live(request):
    return JsonResponse({"status": "ok"})


@require_POST
def switch_context(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) - {"grant_id"}:
            raise ValueError
        selected = data.get("grant_id")
        if selected is not None and not isinstance(selected, str):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"code": "invalid_context"}, status=400)
    previous = request.session.get("active_grant_id")
    request.session["active_grant_id"] = selected
    try:
        epoch = AuthorizationContext(request).epoch()
    except AccessDenied:
        request.session["active_grant_id"] = previous
        return JsonResponse({"code": "context_unavailable"}, status=404)
    import uuid

    return JsonResponse(
        {
            "operation_id": str(uuid.uuid4()),
            "status": "context_changed",
            "context_reset_required": True,
            "next_permission_epoch": epoch,
        }
    )
