"""Local automatic entry is scoped to the explicit loopback development origin."""

import pytest
from accounts.models import Account
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def desktop(settings):
    settings.HEALTH03_LOCAL_DESKTOP = True
    settings.ENVIRONMENT = "development"
    settings.FRONTEND_ORIGIN = "https://localhost:5173"
    settings.API_ORIGIN = "https://localhost:8443"
    settings.CSRF_TRUSTED_ORIGINS = ["https://localhost:5173"]
    return Client(enforce_csrf_checks=True, HTTP_HOST="localhost:8443")


def enter(client, origin="https://localhost:5173", peer="127.0.0.1", csrf=True):
    token = client.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]
    return client.post(
        "/internal/local-session",
        {},
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN=origin,
        REMOTE_ADDR=peer,
        HTTP_X_CSRFTOKEN=token if csrf else "",
    )


def test_local_entry_and_csrf(desktop):
    assert enter(desktop, csrf=False).status_code == 403
    assert enter(desktop).status_code == 200
    assert desktop.get("/api/v1/session", secure=True).json()["role"] == "owner"
    owner = Account.objects.get(email="local-owner@health03.invalid")
    assert not owner.has_usable_password()


@pytest.mark.parametrize(
    "origin,peer",
    [("https://other.invalid", "127.0.0.1"), ("https://localhost:5173", "192.0.2.10")],
)
def test_reject_external_entry(desktop, origin, peer):
    assert enter(desktop, origin, peer).status_code in (403, 404)
    assert not Account.objects.exists()


def test_never_impersonate_existing_owner(desktop):
    Account.objects.create_user("other@example.invalid", role="owner", enrollment_complete=True)
    assert enter(desktop).status_code == 403


def test_disabled_outside_development(desktop, settings):
    settings.ENVIRONMENT = "production"
    assert enter(desktop).status_code == 404


def test_production_appliance_requires_authenticated_loopback_proxy(desktop, settings):
    settings.ENVIRONMENT = "production"
    settings.LOCAL_PROXY_SECRET = "synthetic-desktop"
    settings.TRUSTED_TUNNEL_SECRET = "synthetic-tunnel"
    url = "/api/v1/auth/bootstrap"
    assert desktop.get(url, secure=True).status_code == 403
    desktop.defaults["HTTP_X_HEALTH03_DESKTOP"] = settings.LOCAL_PROXY_SECRET
    assert enter(desktop, peer="192.0.2.1").status_code == 403
    assert enter(desktop, csrf=False).status_code == 403
    assert enter(desktop).status_code == 200
    settings.HEALTH03_UPLOAD_HOST = "phone.example.org"
    settings.ALLOWED_HOSTS = ["localhost", settings.HEALTH03_UPLOAD_HOST]
    assert (
        desktop.post(
            "/internal/local-session",
            HTTP_HOST=settings.HEALTH03_UPLOAD_HOST,
            HTTP_X_FORWARDED_PROTO="https",
        ).status_code
        == 404
    )
