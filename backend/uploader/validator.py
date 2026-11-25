import hashlib

from accounts.policy import eligible
from django.conf import settings
from django.utils import timezone
from oauth2_provider.models import RefreshToken
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2 import InvalidGrantError

from .models import AccessBinding, CodeBinding, TokenFamily
from .policy import ABSOLUTE, family_active, revoke_family


class UploaderValidator(OAuth2Validator):
    def validate_client_id(self, client_id, request, *args, **kwargs):
        return client_id == settings.UPLOADER_CLIENT_ID and super().validate_client_id(
            client_id, request, *args, **kwargs
        )

    def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
        return (
            client_id == settings.UPLOADER_CLIENT_ID
            and grant_type in {"authorization_code", "refresh_token"}
            and super().validate_grant_type(client_id, grant_type, client, request, *args, **kwargs)
        )

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        return (
            bool(scopes)
            and set(scopes) <= {"ingest:write", "ingest:status"}
            and super().validate_scopes(client_id, scopes, client, request, *args, **kwargs)
        )

    def save_authorization_code(self, client_id, code, request, *args, **kwargs):
        device = getattr(request, "health03_device", None)
        if device is None or device.owner_id != request.user.pk or device.revoked_at:
            raise InvalidGrantError()
        grant = self._create_authorization_code(request, code)
        CodeBinding.objects.create(
            grant=grant, device=device, security_epoch=request.user.security_epoch
        )

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        if not super().validate_code(client_id, code, client, request, *args, **kwargs):
            return False
        binding = (
            CodeBinding.objects.select_related("device__owner")
            .filter(grant__code=code, grant__application=client)
            .first()
        )
        if not binding or binding.device.revoked_at or not eligible(binding.device.owner):
            return False
        if (
            binding.device.owner.role != "owner"
            or binding.security_epoch != binding.device.owner.security_epoch
        ):
            return False
        request.health03_device = binding.device
        return True

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        if not super().validate_refresh_token(refresh_token, client, request, *args, **kwargs):
            replay = RefreshToken.objects.filter(
                token_checksum=hashlib.sha256(refresh_token.encode()).hexdigest(),
                application=client,
                revoked__isnull=False,
            ).first()
            if replay is not None:
                revoke_family(replay.token_family)
            return False
        family = (
            TokenFamily.objects.select_related("device__owner")
            .filter(pk=request.refresh_token_instance.token_family)
            .first()
        )
        if family is None or not family_active(family):
            return False
        request.health03_device = family.device
        return True

    def validate_bearer_token(self, token, scopes, request):
        if not super().validate_bearer_token(token, scopes, request):
            return False
        binding = (
            AccessBinding.objects.select_related("family__device__owner")
            .filter(token=request.access_token)
            .first()
        )
        if binding is None or not family_active(binding.family):
            return False
        # Toolkit replay/revocation also has to invalidate access, independent of cached state.
        if not RefreshToken.objects.filter(
            token_family=binding.family_id, revoked__isnull=True
        ).exists():
            return False
        request.health03_device = binding.device
        return True

    def _create_refresh_token(
        self, request, refresh_token_code, access_token, previous_refresh_token
    ):
        device = request.health03_device
        now = timezone.now()
        if previous_refresh_token is None and device.active_family:
            revoke_family(device.active_family)
        token = super()._create_refresh_token(
            request, refresh_token_code, access_token, previous_refresh_token
        )
        if previous_refresh_token is None:
            family = TokenFamily.objects.create(
                id=token.token_family,
                device=device,
                security_epoch=device.owner.security_epoch,
                family_authorized_at=now,
                absolute_expires_at=now + ABSOLUTE,
                last_successful_refresh_at=now,
            )
            device.active_family = family.pk
            device.save(update_fields=["active_family"])
        else:
            family = TokenFamily.objects.get(pk=token.token_family)
            family.last_successful_refresh_at = now
            family.save(update_fields=["last_successful_refresh_at"])
        AccessBinding.objects.create(token=access_token, device=device, family=family)
        return token
