import hashlib
from datetime import timedelta

import pytest
from accounts.models import Account
from allauth.account.models import EmailAddress
from django.test import RequestFactory
from django.utils import timezone
from uploader.backend import UploaderCore
from uploader.models import DeviceAPIKey, DeviceRegistration

pytestmark = pytest.mark.django_db


def test_persistent_key_scope_lifetime_and_revocation(settings):
    owner = Account.objects.create_user(
        'key-owner@example.invalid', role='owner', enrollment_complete=True
    )
    EmailAddress.objects.create(user=owner, email=owner.email, verified=True)
    device = DeviceRegistration.objects.create(owner=owner, label='Test phone')
    raw = 'h03_' + 'a' * 64
    credential = DeviceAPIKey.objects.create(
        device=device, digest=hashlib.sha256(raw.encode()).hexdigest()
    )
    DeviceAPIKey.objects.filter(pk=credential.pk).update(
        created_at=timezone.now() - timedelta(days=730)
    )
    factory = RequestFactory()
    request = factory.get('/api/v1/ingestion/config', HTTP_X_API_KEY=raw)
    core = UploaderCore()
    assert core.verify_request(request, ['ingest:status'])[0]
    assert core.verify_request(request, ['ingest:write'])[0]
    assert not core.verify_request(request, ['clinical:read'])[0]
    assert not core.verify_request(
        factory.get('/', HTTP_X_API_KEY='h03_' + 'b' * 64), ['ingest:write']
    )[0]
    request.COOKIES[settings.SESSION_COOKIE_NAME] = 'browser-session'
    assert not core.verify_request(request, ['ingest:write'])[0]
    request.COOKIES.clear()
    mixed = factory.get('/', HTTP_X_API_KEY=raw, HTTP_AUTHORIZATION='Bearer ambiguous')
    assert not core.verify_request(mixed, ['ingest:write'])[0]
    owner.is_active = False
    owner.save(update_fields=['is_active'])
    assert not core.verify_request(request, ['ingest:write'])[0]
    owner.is_active = True
    owner.save(update_fields=['is_active'])
    device.revoked_at = timezone.now()
    device.save(update_fields=['revoked_at'])
    assert not core.verify_request(request, ['ingest:write'])[0]
    device.revoked_at = None
    device.save(update_fields=['revoked_at'])
    credential.revoked_at = timezone.now()
    credential.save(update_fields=['revoked_at'])
    assert not core.verify_request(request, ['ingest:write'])[0]
