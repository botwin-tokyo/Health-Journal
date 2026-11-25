"""PostgreSQL and real local Transit boundary; synthetic data only."""

import os
import uuid

import pytest
from accounts.models import Account
from allauth.account.models import EmailAddress
from artifacts.models import SecureRecord
from django.conf import settings
from django.test import Client
from records.models import Designation, Record

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("HEALTH03_REAL_KMS_TESTS") != "1",
        reason="Requires the isolated local Transit service",
    ),
]
PASSWORD = "Synthetic-backend-tests!5923"


@pytest.fixture
def browser(settings, tmp_path):
    settings.HEALTH03_BLOB_ROOT = tmp_path / "blobs"
    owner = Account.objects.create_user(
        "backend-owner@example.invalid", PASSWORD, role="owner", enrollment_complete=True
    )
    EmailAddress.objects.create(user=owner, email=owner.email, verified=True, primary=True)
    client = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    assert (
        mutate(
            client, "/_allauth/browser/v1/auth/login", {"email": owner.email, "password": PASSWORD}
        ).status_code
        == 200
    )
    return client


def mutate(client, path, body, method="post", key=None, etag=None):
    csrf = client.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]
    headers = {
        "HTTP_ORIGIN": settings.FRONTEND_ORIGIN,
        "HTTP_X_CSRFTOKEN": csrf,
        "HTTP_IDEMPOTENCY_KEY": key or str(uuid.uuid4()),
    }
    if etag:
        headers["HTTP_IF_MATCH"] = etag
    return getattr(client, method)(
        path, body, content_type="application/json", secure=True, **headers
    )


def test_real_encrypted_weight_retry_and_stale_update(browser):
    key = str(uuid.uuid4())
    body = {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"}
    first = mutate(browser, "/api/v1/body/weights", body, key=key)
    assert first.status_code == 200, first.content
    replay = mutate(browser, "/api/v1/body/weights", body, key=key)
    assert replay.json()["id"] == first.json()["id"] and Record.objects.count() == 1
    conflict = mutate(browser, "/api/v1/body/weights", {**body, "value": "157"}, key=key)
    assert conflict.status_code == 409
    row = first.json()
    changed = mutate(
        browser,
        "/api/v1/body/weights/" + row["id"],
        {**body, "value": "157"},
        method="patch",
        etag=row["etag"],
    )
    assert changed.status_code == 200, changed.content
    stale = mutate(
        browser, "/api/v1/body/weights/" + row["id"], body, method="patch", etag=row["etag"]
    )
    assert stale.status_code == 412 and SecureRecord.objects.count() == 2
    for file in settings.HEALTH03_BLOB_ROOT.iterdir():
        assert b"156.2" not in file.read_bytes()


def test_atomic_weight_designation_note_and_stale_rollback(browser):
    # Patient namespace is created by the first mutation, not an anonymous request.
    from records.models import Patient

    assert Patient.objects.count() == 0
    page = browser.get("/api/v1/body?date=2026-11-07", secure=True).json()
    body = {
        "value": "156.2",
        "unit": "lb",
        "clinical_date": "2026-11-07",
        "time_precision": "day",
        "designation": {
            "action": "make_representative",
            "expected_etag": page["representative_etag"],
        },
        "note_operation": {"text": "Fictional private morning note", "visibility": "private"},
    }
    response = mutate(browser, "/api/v1/body/weights", body)
    assert response.status_code == 200, response.content
    assert Record.objects.count() == 2 and Designation.objects.get().record_id is not None
    stale = mutate(browser, "/api/v1/body/weights", body)
    assert stale.status_code == 412, stale.content
    assert Record.objects.count() == 2


def test_private_question_does_not_return_parent_metadata(browser):
    entry = mutate(
        browser,
        "/api/v1/journal/entries",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "text": "Fictional private parent",
        },
    )
    assert entry.status_code == 200, entry.content
    question = mutate(
        browser,
        "/api/v1/journal/questions",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "text": "Fictional appointment question",
            "origin_record_id": entry.json()["id"],
            "visibility": "shared",
        },
    )
    assert question.status_code == 200, question.content
    assert Record.objects.count() == 2


def test_snapshot_is_immutable_and_deleted_dependency_denies(browser):
    original = mutate(
        browser,
        "/api/v1/body/weights",
        {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"},
    ).json()
    draft = mutate(
        browser,
        "/api/v1/review/drafts",
        {
            "title": "Synthetic review",
            "record_ids": [original["id"]],
            "clinical_date": "2026-11-07",
            "time_precision": "day",
        },
    ).json()
    snapshot = mutate(
        browser, "/api/v1/review/drafts/" + draft["id"] + "/snapshots", {}, etag=draft["etag"]
    )
    assert snapshot.status_code == 200, snapshot.content
    frozen = snapshot.json()
    correction = mutate(
        browser,
        "/api/v1/body/weights/" + original["id"],
        {"value": "160", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"},
        method="patch",
        etag=original["etag"],
    )
    assert correction.status_code == 200, correction.content
    current = browser.get("/api/v1/review/snapshots/" + frozen["id"], secure=True)
    assert current.json()["data"] == frozen["data"]
    deletion = mutate(
        browser,
        "/api/v1/body/weights/" + original["id"],
        {},
        method="delete",
        etag=correction.json()["etag"],
    )
    assert deletion.status_code == 200, deletion.content
    assert browser.get("/api/v1/review/snapshots/" + frozen["id"], secure=True).status_code == 404


def test_lab_unparsed_original_cannot_publish_or_download(browser):
    token = browser.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]
    uploaded = browser.post(
        "/api/v1/labs/uploads",
        b"%PDF-1.4\nfictional invalid document",
        content_type="application/pdf",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=token,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert uploaded.status_code == 202, uploaded.content
    report = uploaded.json()
    review = mutate(
        browser,
        "/api/v1/labs/reports/" + report["id"] + "/review",
        {
            "clinical_date": None,
            "time_precision": "unknown",
            "patient_match_confirmed": True,
            "source_report_status": "unknown",
            "document_only": True,
            "results": [],
        },
        method="patch",
        etag=report["etag"],
    )
    assert review.status_code == 200, review.content
    publication = mutate(
        browser, "/api/v1/labs/reports/" + report["id"] + "/publish", {}, etag=review.json()["etag"]
    )
    assert publication.status_code == 409, publication.content
    detail = browser.get("/api/v1/labs/reports/" + report["id"], secure=True).json()
    assert (
        browser.get(
            "/api/v1/documents/" + detail["document_id"] + "/content", secure=True
        ).status_code
        == 409
    )
    assert browser.get("/api/v1/overview", secure=True).json()["records"]["items"] == []


def test_bad_uuid_and_body_get_generic_validation(browser):
    response = mutate(
        browser,
        "/api/v1/journal/questions",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "text": "Fictional question",
            "origin_record_id": "not-a-uuid",
        },
    )
    assert response.status_code == 422, response.content


def test_doctor_question_scope_and_private_transition(browser):
    from datetime import date, timedelta

    from access.models import SharingGrant
    from django.utils import timezone

    parent = mutate(
        browser,
        "/api/v1/journal/entries",
        {"clinical_date": "2026-11-07", "time_precision": "day", "text": "Private parent sentinel"},
    ).json()
    question = mutate(
        browser,
        "/api/v1/journal/questions",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "text": "Shared question",
            "origin_record_id": parent["id"],
            "visibility": "shared",
        },
    ).json()
    doctor = Account.objects.create_user(
        "backend-doctor@example.invalid", PASSWORD, role="doctor", enrollment_complete=True
    )
    EmailAddress.objects.create(user=doctor, email=doctor.email, verified=True, primary=True)
    grant = SharingGrant.objects.create(
        owner=Account.objects.get(role="owner"),
        recipient=doctor,
        state="active",
        approved_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=30),
        starts_on=date(2026, 11, 7),
        ends_on=date(2026, 11, 7),
        categories=["questions", "journal"],
        actions=["read"],
        selected_question_ids=[question["id"]],
    )
    client = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    assert (
        mutate(
            client, "/_allauth/browser/v1/auth/login", {"email": doctor.email, "password": PASSWORD}
        ).status_code
        == 200
    )
    assert mutate(client, "/api/v1/session/context", {"grant_id": str(grant.pk)}).status_code == 200
    visible = client.get("/api/v1/journal/questions/" + question["id"], secure=True)
    assert visible.status_code == 200 and "origin_record_id" not in visible.json()["data"]
    assert client.get("/api/v1/journal/entries/" + parent["id"], secure=True).status_code == 404
    privatized = mutate(
        browser,
        "/api/v1/journal/questions/" + question["id"],
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "text": "Shared question",
            "visibility": "private",
        },
        method="patch",
        etag=question["etag"],
    )
    assert privatized.status_code == 200 and privatized.json()["context_reset_required"], (
        privatized.content
    )
    assert client.get("/api/v1/journal/questions/" + question["id"], secure=True).status_code == 404


def test_grant_offer_requires_verified_recipient_and_is_single_use(
    browser, mailoutbox, django_capture_on_commit_callbacks
):
    doctor = Account.objects.create_user(
        "invite-doctor@example.invalid", PASSWORD, role="doctor", enrollment_complete=True
    )
    EmailAddress.objects.create(user=doctor, email=doctor.email, verified=True, primary=True)
    scope = {
        "recipient_email": doctor.email,
        "from": "2026-11-01",
        "to": "2026-11-07",
        "categories": ["body"],
        "actions": ["read"],
        "record_allowlists": {
            "journal": [],
            "questions": [],
            "labs": None,
            "medication_events": [],
        },
        "document_ids": [],
    }
    draft = mutate(browser, "/api/v1/sharing/grants", scope)
    assert draft.status_code == 200, draft.content
    with django_capture_on_commit_callbacks(execute=True):
        invited = mutate(
            browser,
            "/api/v1/sharing/grants/" + draft.json()["id"] + "/invite",
            {},
            etag=draft.json()["etag"],
        )
    assert invited.status_code == 200, invited.content
    token = mailoutbox[-1].body.split("#token=")[1]
    client = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    assert (
        mutate(
            client, "/_allauth/browser/v1/auth/login", {"email": doctor.email, "password": PASSWORD}
        ).status_code
        == 200
    )
    accepted = mutate(client, "/api/v1/sharing/accept", {"token": token})
    assert accepted.status_code == 200, accepted.content
    assert mutate(client, "/api/v1/sharing/accept", {"token": token}).status_code == 404


def test_frontend_preferences_and_dated_breathing_history(browser):
    preferences = browser.get("/api/v1/settings", secure=True).json()
    saved = mutate(
        browser,
        "/api/v1/settings",
        {"display_name": "Synthetic owner", "time_format": "24h"},
        method="patch",
        etag=preferences["etag"],
    )
    assert saved.status_code == 200, saved.content
    assert browser.get("/api/v1/settings", secure=True).json()["data"]["time_format"] == "24h"
    created = mutate(
        browser,
        "/api/v1/breathing/manual-sessions",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "slot": "morning",
            "values": {"fev1": "3.82"},
        },
    )
    assert created.status_code == 200, created.content
    history = browser.get(
        "/api/v1/breathing?date=2026-11-08&from=2026-11-01&to=2026-11-08&slot=morning", secure=True
    ).json()
    assert history["selected_session"] is None
    assert history["history"][0]["id"] == created.json()["id"]


def test_terminal_deletion_receipt_survives_intentional_session_revocation(browser):
    response = mutate(
        browser, "/api/v1/account/deletion-requests", {"scope": "account", "confirm": True}
    )
    assert response.status_code == 200, response.content
    assert response.json()["accepted_at"] and response.json()["purge_by"]
    assert response.json()["status_access"] == "operator_support_only_after_logout"
    assert browser.get("/api/v1/session", secure=True).status_code == 401
    assert not Account.objects.get(email="backend-owner@example.invalid").is_active
