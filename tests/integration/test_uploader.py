import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from accounts.models import Account
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import AccessToken, Grant, RefreshToken
from uploader.models import DeviceRegistration, TokenFamily

pytestmark = pytest.mark.django_db
PASSWORD = "Synthetic-uploader-only!327"
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)


@pytest.fixture
def browser():
    user = Account.objects.create_user(
        "owner@example.invalid", PASSWORD, role="owner", enrollment_complete=True
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    browser = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    assert (
        browser.post(
            "/_allauth/browser/v1/auth/login",
            {"email": user.email, "password": PASSWORD},
            content_type="application/json",
            secure=True,
            HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
            HTTP_X_CSRFTOKEN=csrf(browser),
        ).status_code
        == 200
    )
    call_command("register_uploader")
    return browser


def csrf(browser):
    return browser.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]


def parameters(**overrides):
    return {
        "client_id": settings.UPLOADER_CLIENT_ID,
        "redirect_uri": settings.UPLOADER_CALLBACK,
        "response_type": "code",
        "scope": "ingest:write ingest:status",
        "state": "synthetic-state",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        **overrides,
    }


def authorize(browser, existing_device=""):
    response = browser.get("/o/authorize/?" + urlencode(parameters()), secure=True)
    assert response.status_code == 302, response.content
    continuation = response["Location"]
    assert browser.get(continuation, secure=True).status_code == 200
    response = browser.post(
        continuation,
        {"label": "Synthetic phone", "allow": "yes", "existing_device": existing_device},
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=csrf(browser),
    )
    assert response.status_code == 302, response.content
    callback = parse_qs(urlparse(response["Location"]).query)
    assert callback["iss"] == [settings.API_ORIGIN]
    assert callback["state"] == ["synthetic-state"]
    return callback["code"][0]


def token_request(data, client=None):
    client = client or Client(HTTP_HOST="api.health03.test")
    return client.post(
        "/o/token/",
        urlencode({"client_id": settings.UPLOADER_CLIENT_ID, **data}),
        content_type="application/x-www-form-urlencoded",
        secure=True,
    )


def exchange(code, **overrides):
    return token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.UPLOADER_CALLBACK,
            "code_verifier": VERIFIER,
            **overrides,
        }
    )


def refresh(token, **overrides):
    return token_request({"grant_type": "refresh_token", "refresh_token": token, **overrides})


def config(token, client=None):
    return (client or Client(HTTP_HOST="api.health03.test")).get(
        "/api/v1/ingestion/config", secure=True, HTTP_AUTHORIZATION="Bearer " + token
    )


def test_code_exchange_bound_device_and_hash_only_tokens(browser):
    code = authorize(browser)
    response = exchange(code, device_id="attacker-controlled", owner_id="attacker-controlled")
    assert response.status_code == 200, response.content
    result = response.json()
    assert result["expires_in"] == 300
    assert set(result["scope"].split()) == {"ingest:write", "ingest:status"}
    assert all(token == "" for token in AccessToken.objects.values_list("token", flat=True))
    assert all(token == "" for token in RefreshToken.objects.values_list("token", flat=True))
    assert (
        AccessToken.objects.get().token_checksum
        == hashlib.sha256(result["access_token"].encode()).hexdigest()
    )
    device = DeviceRegistration.objects.get()
    assert config(result["access_token"]).json()["device_id"] == str(device.pk)
    assert not Grant.objects.exists()
    assert exchange(code).status_code == 400
    assert (
        browser.get(
            "/api/v1/session", secure=True, HTTP_AUTHORIZATION="Bearer " + result["access_token"]
        ).status_code
        == 401
    )
    assert config(result["access_token"], browser).status_code == 401


@pytest.mark.parametrize(
    "override",
    [
        {"code_verifier": "incorrect" * 8},
        {"redirect_uri": "https://evil.invalid/callback"},
    ],
)
def test_bad_exchange_denied(browser, override):
    response = exchange(authorize(browser), **override)
    assert response.status_code == 400, response.content
    assert not AccessToken.objects.exists()


@pytest.mark.parametrize(
    "override",
    [
        {"code_challenge_method": "plain"},
        {"redirect_uri": "https://evil.invalid/callback"},
        {"response_type": "token"},
        {"scope": "history:read"},
        {"client_id": "unregistered"},
    ],
)
def test_invalid_authorization_never_redirects_to_untrusted_callback(browser, override):
    response = browser.get("/o/authorize/?" + urlencode(parameters(**override)), secure=True)
    assert response.status_code == 400, response.content
    assert not DeviceRegistration.objects.exists()


def test_rotation_replay_revokes_family_and_requires_reconnect(browser):
    first = exchange(authorize(browser)).json()
    rotated = refresh(first["refresh_token"])
    assert rotated.status_code == 200, rotated.content
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert config(first["access_token"]).status_code == 401
    assert config(second["access_token"]).status_code == 200
    assert refresh(first["refresh_token"]).status_code == 400
    assert config(second["access_token"]).status_code == 401
    assert refresh(second["refresh_token"]).status_code == 400
    assert RefreshToken.objects.count() == 2  # retain family replay evidence
    reconnected = exchange(authorize(browser))
    assert reconnected.status_code == 200
    assert config(reconnected.json()["access_token"]).status_code == 200


@pytest.mark.parametrize(
    "field,value",
    [
        ("absolute_expires_at", lambda: timezone.now() - timedelta(seconds=1)),
        ("last_successful_refresh_at", lambda: timezone.now() - timedelta(days=31)),
    ],
)
def test_device_lifetime_checked_without_cleanup(browser, field, value):
    issued = exchange(authorize(browser)).json()
    TokenFamily.objects.update(**{field: value()})
    assert config(issued["access_token"]).status_code == 401
    assert refresh(issued["refresh_token"]).status_code == 400


def test_owner_revocation_is_immediate(browser):
    issued = exchange(authorize(browser)).json()
    device = DeviceRegistration.objects.get()
    response = browser.post(
        f"/api/v1/devices/{device.pk}/revoke",
        {},
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=csrf(browser),
    )
    assert response.status_code == 200
    assert config(issued["access_token"]).status_code == 401
    assert refresh(issued["refresh_token"]).status_code == 400


def test_scope_cannot_expand_and_browser_cannot_exchange(browser):
    issued = exchange(authorize(browser)).json()
    assert refresh(issued["refresh_token"], scope="history:read").status_code == 400
    assert (
        token_request(
            {"grant_type": "refresh_token", "refresh_token": issued["refresh_token"]}, browser
        ).status_code
        == 400
    )


def test_continuation_bound_to_browser_and_no_free_return_url(browser):
    response = browser.get("/o/authorize/?" + urlencode(parameters()), secure=True)
    stranger = Client(HTTP_HOST="api.health03.test")
    assert stranger.get(response["Location"], secure=True).status_code == 400
    assert (
        browser.get(
            "/o/authorize/?" + urlencode(parameters(return_url="https://evil.invalid")), secure=True
        ).status_code
        == 400
    )


def test_password_change_revokes_native_family(browser):
    issued = exchange(authorize(browser)).json()
    response = browser.post(
        "/_allauth/browser/v1/account/password/change",
        {"current_password": PASSWORD, "new_password": PASSWORD + "next"},
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=csrf(browser),
    )
    assert response.status_code == 200
    assert config(issued["access_token"]).status_code == 401
    assert refresh(issued["refresh_token"]).status_code == 400
    assert TokenFamily.objects.get().revoked_at is not None


def test_consent_requires_csrf_fresh_password_and_owner(browser):
    from accounts.models import SessionSecurity

    response = browser.get("/o/authorize/?" + urlencode(parameters()), secure=True)
    continuation = response["Location"]
    assert (
        browser.post(continuation, {"label": "phone", "allow": "yes"}, secure=True).status_code
        == 403
    )
    SessionSecurity.objects.update(password_verified_at=timezone.now() - timedelta(minutes=6))
    response = browser.get(continuation, secure=True)
    assert response["Location"].startswith(
        settings.FRONTEND_ORIGIN + "/reauthenticate?continuation="
    )
    Account.objects.update(role="doctor")
    assert browser.get(continuation, secure=True).status_code == 403
    assert not DeviceRegistration.objects.exists()


def test_anonymous_authorization_handoff_is_opaque(browser):
    anon = Client(HTTP_HOST="api.health03.test")
    response = anon.get("/o/authorize/?" + urlencode(parameters()), secure=True)
    response = anon.get(response["Location"], secure=True)
    assert response["Location"].startswith(settings.FRONTEND_ORIGIN + "/login?continuation=")
    assert CHALLENGE not in response["Location"]
    assert "redirect_uri" not in response["Location"]


def test_cleanup_preserves_replay_evidence_until_absolute_window_plus_seven_days(browser):
    issued = exchange(authorize(browser)).json()
    refresh(issued["refresh_token"])
    refresh(issued["refresh_token"])
    call_command("prune_native_evidence")
    assert RefreshToken.objects.count() == 2
    TokenFamily.objects.update(absolute_expires_at=timezone.now() - timedelta(days=8))
    call_command("prune_native_evidence")
    assert not RefreshToken.objects.exists()
    assert not TokenFamily.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_replay_revokes_the_rotated_result(browser):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connections

    issued = exchange(authorize(browser)).json()

    def contender(_):
        try:
            response = refresh(issued["refresh_token"])
            return response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(contender, range(2)))
    assert sorted(status for status, body in results) == [200, 400]
    rotated = next(body for status, body in results if status == 200)
    assert config(rotated["access_token"]).status_code == 401
    assert refresh(rotated["refresh_token"]).status_code == 400


def test_reconnect_same_device_replaces_previous_family(browser):
    old = exchange(authorize(browser)).json()
    device = DeviceRegistration.objects.get()
    new = exchange(authorize(browser, str(device.pk)))
    assert new.status_code == 200, new.content
    assert DeviceRegistration.objects.count() == 1
    assert TokenFamily.objects.count() == 2
    assert TokenFamily.objects.filter(revoked_at__isnull=True).count() == 1
    assert config(old["access_token"]).status_code == 401
    assert refresh(old["refresh_token"]).status_code == 400
    assert config(new.json()["access_token"]).status_code == 200


def test_query_bearer_and_expired_access_denied(browser):
    issued = exchange(authorize(browser)).json()
    machine = Client(HTTP_HOST="api.health03.test")
    response = machine.get(
        "/api/v1/ingestion/config?" + urlencode({"access_token": issued["access_token"]}),
        secure=True,
        HTTP_AUTHORIZATION="Bearer " + issued["access_token"],
    )
    assert response.status_code == 401
    AccessToken.objects.update(expires=timezone.now() - timedelta(seconds=1))
    assert config(issued["access_token"]).status_code == 401
    assert refresh(issued["refresh_token"]).status_code == 200
