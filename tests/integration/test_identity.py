import secrets
from datetime import timedelta

import pytest
from accounts.adapter import token_hash
from accounts.models import Account, Invitation, SessionSecurity
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db
PASSWORD = "Fictional-test-only!8462"
AUTH = "/_allauth/browser/v1/"


@pytest.fixture
def browser():
    return Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")


def csrf(browser):
    return browser.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]


def post(browser, path, data=None, token=None):
    return browser.post(
        path,
        data or {},
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN="https://dashboard.health03.test",
        HTTP_X_CSRFTOKEN=token or csrf(browser),
    )


@pytest.fixture
def owner():
    user = Account.objects.create_user(
        "owner@example.invalid", PASSWORD, role="owner", enrollment_complete=True
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def login(browser, user, password=PASSWORD):
    return post(browser, AUTH + "auth/login", {"email": user.email, "password": password})


def test_public_bootstrap_and_protected_session(browser):
    result = browser.get("/api/v1/auth/bootstrap", secure=True)
    assert set(result.json()) == {"csrf_token", "login_method", "signup"}
    assert "no-store" in result["Cache-Control"]
    assert browser.get("/api/v1/session", secure=True).status_code == 401


def test_login_requires_csrf(browser, owner):
    response = browser.post(
        AUTH + "auth/login",
        {"email": owner.email, "password": PASSWORD},
        content_type="application/json",
        secure=True,
    )
    assert response.status_code == 403
    assert SessionSecurity.objects.count() == 0


def test_password_login_session_and_logout(browser, owner):
    response = login(browser, owner)
    assert response.status_code == 200, response.content
    response = browser.get("/api/v1/session", secure=True)
    assert response.status_code == 200, response.content
    assert response.json()["role"] == "owner"
    assert response["X-Permission-Epoch"] == response.json()["permission_epoch"]
    assert response["X-Permission-Epoch"] != str(owner.security_epoch)
    cookie = browser.cookies["__Host-health03_session"]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
    assert cookie["path"] == "/" and not cookie["domain"]
    response = browser.delete(
        AUTH + "auth/session",
        secure=True,
        HTTP_ORIGIN="https://dashboard.health03.test",
        HTTP_X_CSRFTOKEN=csrf(browser),
    )
    assert response.status_code in {200, 401}
    assert browser.get("/api/v1/session", secure=True).status_code == 401


@pytest.mark.parametrize("condition", ["wrong_password", "unverified", "incomplete", "inactive"])
def test_ineligible_login_has_no_application_access(browser, owner, condition):
    if condition == "unverified":
        EmailAddress.objects.update(verified=False)
    elif condition == "incomplete":
        owner.enrollment_complete = False
        owner.save()
    elif condition == "inactive":
        owner.is_active = False
        owner.save()
    login(browser, owner, "wrong-password" if condition == "wrong_password" else PASSWORD)
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert SessionSecurity.objects.count() == 0


@pytest.mark.parametrize("field", ["idle_expires_at", "absolute_expires_at"])
def test_expired_session_cannot_read_or_refresh(browser, owner, field):
    assert login(browser, owner).status_code == 200
    SessionSecurity.objects.update(**{field: timezone.now() - timedelta(seconds=1)})
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert post(browser, "/api/v1/session/activity").status_code == 401


def test_polling_does_not_extend_activity(browser, owner):
    login(browser, owner)
    state = SessionSecurity.objects.get()
    browser.get("/api/v1/session", secure=True)
    assert SessionSecurity.objects.get().idle_expires_at == state.idle_expires_at
    response = post(browser, "/api/v1/session/activity")
    assert response.status_code == 200
    updated = SessionSecurity.objects.get()
    assert updated.idle_expires_at > state.idle_expires_at
    assert updated.absolute_expires_at == state.absolute_expires_at


def test_bearer_rejected_on_browser_api(browser, owner):
    login(browser, owner)
    response = browser.get("/api/v1/session", secure=True, HTTP_AUTHORIZATION="Bearer fictional")
    assert response.status_code == 401


def test_no_public_signup(browser):
    response = post(
        browser, AUTH + "auth/signup", {"email": "stranger@example.invalid", "password": PASSWORD}
    )
    assert response.status_code in {400, 403}, response.content
    assert not Account.objects.exists()


def test_enrollment_email_binding_and_single_use(browser):
    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        email="owner@example.invalid",
        role="owner",
        secret_hash=token_hash(token),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    assert post(browser, "/api/v1/auth/invitation", {"token": token}).status_code == 200
    response = post(
        browser, AUTH + "auth/signup", {"email": "wrong@example.invalid", "password": PASSWORD}
    )
    assert response.status_code == 400, response.content
    response = post(
        browser, AUTH + "auth/signup", {"email": invitation.email, "password": PASSWORD}
    )
    assert response.status_code in {200, 401}, response.content
    invitation.refresh_from_db()
    assert invitation.consumed_at is not None
    user = Account.objects.get(email=invitation.email)
    assert user.role == "owner" and user.check_password(PASSWORD)
    assert user.password != PASSWORD
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert post(browser, "/api/v1/auth/invitation", {"token": token}).status_code == 400


def test_credential_epoch_invalidates_existing_session(browser, owner):
    import uuid

    login(browser, owner)
    Account.objects.filter(pk=owner.pk).update(security_epoch=uuid.uuid4())
    assert browser.get("/api/v1/session", secure=True).status_code == 401


def test_step_up_and_password_change_revokes_other_session(browser, owner):
    other = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    login(browser, owner)
    login(other, owner)
    SessionSecurity.objects.update(password_verified_at=timezone.now() - timedelta(minutes=6))
    data = {"current_password": PASSWORD, "new_password": PASSWORD + "next"}
    assert post(browser, AUTH + "account/password/change", data).status_code == 403
    response = post(browser, AUTH + "auth/reauthenticate", {"password": PASSWORD})
    assert response.status_code == 200, response.content
    response = post(browser, AUTH + "account/password/change", data)
    assert response.status_code in {200, 401}, response.content
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert other.get("/api/v1/session", secure=True).status_code == 401
    owner.refresh_from_db()
    assert owner.check_password(PASSWORD + "next")


def test_json_cache_atomic_add_expiry_increment():
    assert cache.add("counter", 1, 60)
    assert not cache.add("counter", 9, 60)
    assert cache.incr("counter") == 2
    cache.set("expired", "private", -1)
    assert cache.get("expired") is None
    assert cache.add("expired", "replacement", 60)
    assert cache.get("expired") == "replacement"


def test_cross_origin_policy(browser):
    response = browser.get(
        "/api/v1/auth/bootstrap", secure=True, HTTP_ORIGIN="https://evil.invalid"
    )
    assert "Access-Control-Allow-Origin" not in response
    response = browser.get(
        "/api/v1/auth/bootstrap", secure=True, HTTP_ORIGIN="https://dashboard.health03.test"
    )
    assert response["Access-Control-Allow-Origin"] == "https://dashboard.health03.test"
    assert response["Access-Control-Allow-Credentials"] == "true"


def test_reset_mail_restricted_and_reset_requires_login(browser, owner, mailoutbox):
    import re

    authenticated = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    login(authenticated, owner)
    unknown = post(browser, AUTH + "auth/password/request", {"email": "unknown@example.invalid"})
    known = post(browser, AUTH + "auth/password/request", {"email": owner.email})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert len(mailoutbox) == 1
    key = re.search(
        r"https://dashboard.health03.test/reset-password/([^\s]+)", mailoutbox[0].body
    ).group(1)
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    response = post(
        browser, AUTH + "auth/password/reset", {"key": key, "password": PASSWORD + "reset"}
    )
    assert response.status_code == 200, response.content
    assert response.json()["login_required"] is True
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert authenticated.get("/api/v1/session", secure=True).status_code == 401
    assert (
        post(
            browser, AUTH + "auth/password/reset", {"key": key, "password": PASSWORD + "again"}
        ).status_code
        == 400
    )
    assert login(browser, owner, PASSWORD + "reset").status_code == 200


def test_unverified_address_receives_no_reset(browser, owner, mailoutbox):
    EmailAddress.objects.update(verified=False)
    assert post(browser, AUTH + "auth/password/request", {"email": owner.email}).status_code == 200
    assert len(mailoutbox) == 0


def test_email_verification_is_not_password_login(browser):
    from allauth.account.models import EmailConfirmationHMAC

    user = Account.objects.create_user(
        "doctor@example.invalid", PASSWORD, role="doctor", enrollment_complete=True
    )
    address = EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    key = EmailConfirmationHMAC(address).key
    response = post(browser, AUTH + "auth/email/verify", {"key": key})
    assert response.status_code in {200, 401}, response.content
    address.refresh_from_db()
    assert address.verified
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert login(browser, user).status_code == 200
    assert browser.get("/api/v1/session", secure=True).json()["capabilities"] == []


def test_failed_password_attempts_are_rate_limited(browser, owner):
    statuses = [login(browser, owner, "incorrect-password").status_code for _ in range(7)]
    assert any(status in {400, 429} for status in statuses)
    response = login(browser, owner)
    assert response.status_code in {400, 429}, response.content
    assert browser.get("/api/v1/session", secure=True).status_code == 401


def test_bootstrap_only_creates_private_hashed_enrollment(monkeypatch, tmp_path):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    handoff = tmp_path / "handoff"
    answers = iter(["owner@example.invalid", str(handoff)])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    call_command("bootstrap_owner")
    invite = Invitation.objects.get()
    assert invite.secret_hash == token_hash(handoff.read_text().strip())
    assert handoff.stat().st_mode & 0o777 == 0o600
    assert not Account.objects.exists()
    answers = iter(["second@example.invalid", str(tmp_path / "second")])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    with pytest.raises(CommandError):
        call_command("bootstrap_owner")
    assert Invitation.objects.count() == 1


def test_activity_never_extends_absolute_deadline(browser, owner):
    login(browser, owner)
    absolute = timezone.now() + timedelta(minutes=1)
    SessionSecurity.objects.update(absolute_expires_at=absolute)
    assert post(browser, "/api/v1/session/activity").status_code == 200
    assert SessionSecurity.objects.get().idle_expires_at == absolute


def test_expired_invitation_and_untrusted_origin_denied(browser):
    token = secrets.token_urlsafe(32)
    Invitation.objects.create(
        email="owner@example.invalid",
        role="owner",
        secret_hash=token_hash(token),
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert post(browser, "/api/v1/auth/invitation", {"token": token}).status_code == 400
    response = browser.post(
        "/api/v1/auth/invitation",
        {"token": token},
        content_type="application/json",
        secure=True,
        HTTP_X_CSRFTOKEN=csrf(browser),
        HTTP_ORIGIN="https://evil.invalid",
    )
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_cache_add_and_increment_concurrent_connections():
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections, connections

    def contender(_):
        close_old_connections()
        try:
            won = cache.add("shared-race", 0, 60)
            cache.incr("shared-race")
            return won
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(contender, range(8)))
    assert sum(results) == 1
    assert cache.get("shared-race") == 8
