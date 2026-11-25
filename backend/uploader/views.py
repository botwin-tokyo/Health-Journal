import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from accounts.adapter import token_hash
from accounts.policy import fresh, session_state
from allauth.core import ratelimit
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.views import RevokeTokenView, TokenView

from .backend import UploaderCore, has_machine_credentials
from .models import AuthorizationContinuation, DeviceRegistration
from .policy import NATIVE_LOCK, revoke_family

PARAMETERS = {
    "client_id",
    "redirect_uri",
    "response_type",
    "scope",
    "state",
    "code_challenge",
    "code_challenge_method",
}


def native_lock():
    # Personal-server throughput boundary: serialize code exchange, rotation and revocation.
    # Invalid-grant responses commit replay revocations; they must not roll back the transaction.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [NATIVE_LOCK])


@require_GET
def authorize(request):
    if not ratelimit.consume(request, action="native_authorization"):
        return JsonResponse({"error": "rate_limited"}, status=429)
    if (
        set(request.GET) - PARAMETERS
        or any(len(v) != 1 for _, v in request.GET.lists())
        or request.GET.get("client_id") != settings.UPLOADER_CLIENT_ID
        or request.GET.get("redirect_uri") != settings.UPLOADER_CALLBACK
        or request.GET.get("response_type") != "code"
        or request.GET.get("code_challenge_method") != "S256"
        or not request.GET.get("state")
    ):
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        UploaderCore().validate_authorization_request(request)
    except OAuthToolkitError:
        return JsonResponse({"error": "invalid_request"}, status=400)
    secret = request.session.get("native_continuation_secret")
    if not secret:
        secret = secrets.token_urlsafe(32)
        request.session["native_continuation_secret"] = secret
    continuation = AuthorizationContinuation.objects.create(
        browser_secret_hash=token_hash(secret),
        parameters=request.GET.dict(),
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    return HttpResponseRedirect(f"/o/continue/{continuation.pk}/")


@require_http_methods(["GET", "POST"])
@transaction.atomic
def continuation(request, continuation_id):
    pending = (
        AuthorizationContinuation.objects.select_for_update()
        .filter(
            pk=continuation_id,
            browser_secret_hash=token_hash(request.session.get("native_continuation_secret", "")),
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if not pending:
        return JsonResponse({"error": "continuation_expired"}, status=400)
    state = session_state(request)
    if state is None:
        return HttpResponseRedirect(
            settings.FRONTEND_ORIGIN + "/login?continuation=" + str(pending.pk)
        )
    if request.user.role != "owner":
        return JsonResponse({"error": "owner_required"}, status=403)
    if not fresh(state):
        return HttpResponseRedirect(
            settings.FRONTEND_ORIGIN + "/reauthenticate?continuation=" + str(pending.pk)
        )
    if request.method == "GET":
        return render(
            request,
            "uploader/consent.html",
            {
                "devices": DeviceRegistration.objects.filter(
                    owner=request.user, revoked_at__isnull=True
                )
            },
        )
    label = request.POST.get("label", "").strip()
    allow = request.POST.get("allow") == "yes"
    if allow and not 1 <= len(label) <= 80:
        return JsonResponse({"error": "invalid_label"}, status=400)
    native_lock()
    request.META["QUERY_STRING"] = urlencode(pending.parameters)
    try:
        scopes, credentials = UploaderCore().validate_authorization_request(request)
    except OAuthToolkitError:
        return JsonResponse({"error": "invalid_request"}, status=400)
    device = None
    created_device = False
    if allow:
        existing_id = request.POST.get("existing_device")
        if existing_id:
            try:
                existing_id = uuid.UUID(existing_id)
            except ValueError:
                return JsonResponse({"error": "invalid_device"}, status=400)
            device = (
                DeviceRegistration.objects.select_for_update()
                .filter(pk=existing_id, owner=request.user, revoked_at__isnull=True)
                .first()
            )
            if device is None:
                return JsonResponse({"error": "invalid_device"}, status=400)
        else:
            device = DeviceRegistration.objects.create(owner=request.user, label=label)
            created_device = True
    request.health03_device = device
    try:
        uri, headers, body, status = UploaderCore().create_authorization_response(
            request, scopes, credentials, allow
        )
    except OAuthToolkitError:
        if created_device:
            device.delete()
        pending.consumed_at = timezone.now()
        pending.save(update_fields=["consumed_at"])
        return JsonResponse({"error": "authorization_denied"}, status=400)
    pending.consumed_at = timezone.now()
    pending.save(update_fields=["consumed_at"])
    return HttpResponse(body or "", status=status, headers=headers)


def machine_credentials_only(request):
    if settings.SESSION_COOKIE_NAME in request.COOKIES:
        return JsonResponse({"error": "ambiguous_credentials"}, status=400)
    if request.content_type != "application/x-www-form-urlencoded":
        return JsonResponse({"error": "invalid_request"}, status=400)
    if not ratelimit.consume(request, action="native_token"):
        return JsonResponse({"error": "rate_limited"}, status=429)
    return None


@csrf_exempt  # Standard form-encoded OAuth endpoint: no browser-session authentication.
@require_POST
@transaction.atomic
def token(request):
    rejected = machine_credentials_only(request)
    if rejected is not None:
        return rejected
    native_lock()
    return TokenView.as_view()(request)


@csrf_exempt  # RFC 7009 machine-token revocation, never authenticates using a browser cookie.
@require_POST
@transaction.atomic
def revoke_token(request):
    rejected = machine_credentials_only(request)
    if rejected is not None:
        return rejected
    native_lock()
    return RevokeTokenView.as_view()(request)


@require_GET
def ingestion_config(request):
    if not has_machine_credentials(request):
        return JsonResponse({"code": "uploader_credentials_required"}, status=401)
    valid, oauth_request = UploaderCore().verify_request(request, scopes=["ingest:status"])
    if not valid:
        return JsonResponse({"code": "uploader_credentials_required"}, status=401)
    return JsonResponse(
        {
            "device_id": str(oauth_request.health03_device.pk),
            "schedule": "00:00",
            "timezone": settings.TIME_ZONE,
            "command_ids": list(
                __import__("ingest.models", fromlist=["SyncRequest"])
                .SyncRequest.objects.filter(
                    device=oauth_request.health03_device, state__in=["queued", "requesting"]
                )
                .values_list("id", flat=True)[:50]
            ),
            "deployed_revision": settings.HEALTH03_DEPLOYED_REVISION,
            "contract_sha256": __import__("hashlib").sha256((__import__("ingest.contract", fromlist=["ROOT"]).ROOT / "batch.schema.json").read_bytes()).hexdigest(),
            "contract_version": __import__("ingest.contract", fromlist=["VERSION"]).VERSION,
            "source_capabilities": {kind: True for kind in __import__("ingest.mapping", fromlist=["SUPPORTED_KINDS"]).SUPPORTED_KINDS},
            "receipt_dispositions": ["clinical", "evidence", "deleted", "none"],
            "limits": {"batch_bytes": 5242880, "batch_items": 1000, "asset_bytes": 26214400, "asset_links_per_item": 100},
            "ingestion_ready": True,
        }
    )


@require_GET
def devices(request):
    if request.user.role != "owner":
        return JsonResponse({"code": "forbidden"}, status=403)
    return JsonResponse(
        {
            "devices": [
                {"id": str(row.pk), "label": row.label, "revoked": row.revoked_at is not None}
                for row in DeviceRegistration.objects.filter(owner=request.user)
            ]
        }
    )


@require_POST
@transaction.atomic
def revoke_device(request, device_id):
    native_lock()
    device = (
        DeviceRegistration.objects.select_for_update()
        .filter(pk=device_id, owner=request.user)
        .first()
    )
    if not device or request.user.role != "owner":
        return JsonResponse({"code": "not_found"}, status=404)
    if device.active_family:
        revoke_family(device.active_family)
    device.revoked_at = timezone.now()
    device.save(update_fields=["revoked_at"])
    from operations import audit, ledger

    ledger.enqueue(request.user.pk, "device_revoked", device.pk)
    audit.emit("device_revoked", request.user, device.pk)
    return JsonResponse({"status": "revoked", "durability": "pending"})
