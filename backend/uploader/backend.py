import hashlib
from types import SimpleNamespace

from accounts.policy import eligible
from django.conf import settings
from oauth2_provider.oauth2_backends import OAuthLibCore

from .models import DeviceAPIKey


def has_machine_credentials(request):
    return settings.SESSION_COOKIE_NAME not in request.COOKIES and (
        bool(request.headers.get("X-API-Key"))
        or request.headers.get("Authorization", "").startswith("Bearer ")
    )


class UploaderCore(OAuthLibCore):
    def verify_request(self, request, scopes):
        key = request.headers.get("X-API-Key")
        if key is None:
            return super().verify_request(request, scopes)
        if (
            settings.SESSION_COOKIE_NAME in request.COOKIES
            or request.headers.get("Authorization")
            or not key.startswith("h03_")
            or len(key) != 68
            or not set(scopes) <= {"ingest:write", "ingest:status"}
        ):
            return False, None
        credential = DeviceAPIKey.objects.select_related("device__owner").filter(
            digest=hashlib.sha256(key.encode()).hexdigest(),
            revoked_at__isnull=True,
            device__revoked_at__isnull=True,
        ).first()
        if credential is None:
            return False, None
        owner = credential.device.owner
        if owner.role != "owner" or not eligible(owner):
            return False, None
        return True, SimpleNamespace(health03_device=credential.device)

    def create_authorization_response(self, request, scopes, credentials, allow):
        credentials["health03_device"] = request.health03_device
        return super().create_authorization_response(request, scopes, credentials, allow)
