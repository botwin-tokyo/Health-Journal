import uuid
from dataclasses import replace
from datetime import date, timedelta

import pytest
from access.models import SharingGrant
from access.policy import AccessDenied, AuthorizationContext, RecordRef
from access.services import approve_grant, revoke_grant
from accounts.models import Account, SessionSecurity
from allauth.account.models import EmailAddress
from crypto.envelopes import EnvelopeService, Identity
from django.conf import settings
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db
PASSWORD = "Fictional-scope-tests!672"


def browser_for(user):
    browser = Client(enforce_csrf_checks=True, HTTP_HOST="api.health03.test")
    response = post(
        browser, "/_allauth/browser/v1/auth/login", {"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    return browser


def post(browser, path, data):
    token = browser.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]
    return browser.post(
        path,
        data,
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=token,
    )


def context(browser):
    return AuthorizationContext(browser.get("/api/v1/session", secure=True).wsgi_request)


@pytest.fixture
def setup():
    users = []
    for name, role in [("owner", "owner"), ("doctor-a", "doctor"), ("doctor-b", "doctor")]:
        user = Account.objects.create_user(
            name + "@example.invalid", PASSWORD, role=role, enrollment_complete=True
        )
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        users.append(user)
    owner, doctor, other = users
    now = timezone.now()
    grant = SharingGrant.objects.create(
        owner=owner,
        recipient=doctor,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 1, 31),
        not_before=now - timedelta(minutes=1),
        expires_at=now + timedelta(days=30),
        categories=["body", "journal", "questions", "labs"],
        actions=["read", "download_report", "read_original_document"],
    )
    owner_browser = browser_for(owner)
    approve_grant(context(owner_browser).request, grant.pk)
    grant.refresh_from_db()
    doctor_browser = browser_for(doctor)
    assert (
        post(doctor_browser, "/api/v1/session/context", {"grant_id": str(grant.pk)}).status_code
        == 200
    )
    return owner, doctor, other, grant, owner_browser, doctor_browser


def record(owner, kind="clinical_record", category="body", **overrides):
    return RecordRef(
        Identity(owner.pk, kind, uuid.uuid4(), uuid.uuid4(), 1),
        category,
        date(2026, 1, 15),
        **overrides,
    )


def test_owner_doctor_context_and_cross_owner_denial(setup):
    owner, doctor, other, grant, ob, db = setup
    item = record(owner)
    assert context(ob).require(item, "write")
    assert context(db).require(item)
    with pytest.raises(AccessDenied):
        context(db).require(item, "write")
    with pytest.raises(AccessDenied):
        context(ob).require(replace(item, identity=replace(item.identity, owner_id=uuid.uuid4())))
    response = post(browser_for(other), "/api/v1/session/context", {"grant_id": str(grant.pk)})
    assert response.status_code == 404
    assert response.json() == {"code": "context_unavailable"}


def test_scope_dates_inclusive_and_categories(setup):
    owner, _, _, _, _, db = setup
    item = record(owner)
    policy = context(db)
    for value in [date(2026, 1, 1), date(2026, 1, 31)]:
        assert policy.require(replace(item, clinical_date=value))
    for value in [date(2025, 12, 31), date(2026, 2, 1)]:
        with pytest.raises(AccessDenied):
            policy.require(replace(item, clinical_date=value))
    with pytest.raises(AccessDenied):
        policy.require(replace(item, category="breathing"))


def test_private_note_and_shared_question_are_independent(setup):
    owner, _, _, grant, _, db = setup
    note = record(owner, "journal_entry", "journal")
    question = record(owner, "appointment_question", "questions", visibility="shared")
    grant.selected_question_ids = [str(question.identity.object_id)]
    grant.selected_entry_ids = [str(note.identity.object_id)]
    grant.save()
    assert context(db).require(question)
    with pytest.raises(AccessDenied):
        context(db).require(note)
    grant.selected_question_ids = []
    grant.save()
    with pytest.raises(AccessDenied):
        context(db).require(question)


def test_original_document_requires_whole_document_consent(setup):
    owner, _, _, grant, _, db = setup
    result = record(owner, category="labs")
    document = replace(record(owner, "lab_document", "labs"), clinical_date=date(2025, 1, 1))
    assert context(db).require(result)
    with pytest.raises(AccessDenied):
        context(db).require(document, "read_original_document")
    grant.whole_document_ids = [str(document.identity.object_id)]
    grant.save()
    assert context(db).require(document, "read_original_document")
    with pytest.raises(AccessDenied):
        context(db).require(document, "read")


def test_optional_result_allowlist_empty_means_none(setup):
    owner, _, _, grant, _, db = setup
    item = record(owner, category="labs")
    assert context(db).require(item)
    grant.selected_result_ids = []
    grant.save()
    with pytest.raises(AccessDenied):
        context(db).require(item)
    grant.selected_result_ids = [str(item.identity.object_id)]
    grant.save()
    assert context(db).require(item)


def test_medication_event_requires_own_date_selection_and_shared_parent(setup):
    owner, _, _, grant, _, db = setup
    parent = record(owner, "journal_entry", "journal", visibility="shared")
    event = record(owner, "medication_event", "journal", visibility="shared", parent=parent)
    grant.selected_entry_ids = [str(parent.identity.object_id)]
    grant.save()
    with pytest.raises(AccessDenied):
        context(db).require(event)
    grant.selected_medication_event_ids = [str(event.identity.object_id)]
    grant.save()
    assert context(db).require(event)
    with pytest.raises(AccessDenied):
        context(db).require(replace(event, clinical_date=date(2025, 12, 1)))
    with pytest.raises(AccessDenied):
        context(db).require(replace(event, parent=replace(parent, visibility="private")))


def test_summary_with_hidden_contributor_is_denied_without_details(setup):
    owner, _, _, _, _, db = setup
    hidden = replace(record(owner), clinical_date=date(2025, 12, 31))
    summary = record(owner, "derived_snapshot", dependencies=(record(owner), hidden))
    with pytest.raises(AccessDenied, match="^Record unavailable$"):
        context(db).require(summary)
    assert context(db).require(replace(summary, dependencies=(record(owner),)))


def test_owner_preview_uses_exact_doctor_policy(setup):
    owner, _, _, grant, ob, _ = setup
    item = replace(record(owner), clinical_date=date(2025, 12, 31))
    before = ob.get("/api/v1/session", secure=True).json()["permission_epoch"]
    assert context(ob).require(item)
    response = post(ob, "/api/v1/session/context", {"grant_id": str(grant.pk)})
    assert response.json()["context_reset_required"] is True
    assert response.json()["next_permission_epoch"] != before
    assert "account_id" not in response.json()
    with pytest.raises(AccessDenied):
        context(ob).require(item)
    assert ob.get("/api/v1/session", secure=True).json()["context"]["view_mode"] == "owner_preview"
    assert post(ob, "/api/v1/session/context", {"grant_id": None}).status_code == 200
    assert context(ob).require(item)


def test_grant_revocation_precedes_cached_decryption(setup):
    owner, _, _, grant, ob, db = setup
    item = record(owner)
    owner_policy = context(ob)
    doctor_policy = context(db)

    class TestKMS:
        def wrap(self, key):
            self.key = key
            return "vault:v1:AA=="

        def unwrap(self, wrapped):
            return self.key

    service = EnvelopeService(TestKMS())
    envelope = service.encrypt(
        b"fictional note", item.identity, owner_policy.envelope_authorizer(item, "write")
    )
    assert (
        service.decrypt(envelope, item.identity, doctor_policy.envelope_authorizer(item))
        == b"fictional note"
    )
    before = context(ob).epoch()
    revoke_grant(context(ob).request, grant.pk)
    assert context(ob).epoch() != before
    with pytest.raises(AccessDenied):
        service.decrypt(envelope, item.identity, doctor_policy.envelope_authorizer(item))
    assert db.get("/api/v1/session", secure=True).status_code == 403
    assert post(db, "/api/v1/session/context", {"grant_id": None}).status_code == 200


@pytest.mark.parametrize(
    "change", ["expired", "not_yet_active", "unverified_recipient", "disabled_recipient"]
)
def test_live_grant_and_account_state_rechecked(setup, change):
    owner, doctor, _, grant, _, db = setup
    policy = context(db)
    assert policy.require(record(owner))
    if change == "expired":
        grant.expires_at = timezone.now() - timedelta(seconds=1)
        grant.save()
    elif change == "not_yet_active":
        grant.not_before = timezone.now() + timedelta(minutes=1)
        grant.save()
    elif change == "unverified_recipient":
        EmailAddress.objects.filter(user=doctor).update(verified=False)
    else:
        Account.objects.filter(pk=doctor.pk).update(is_active=False)
    with pytest.raises(AccessDenied):
        policy.require(record(owner))


def test_approval_requires_fresh_password_and_bounded_expiry(setup):
    _, _, _, grant, ob, _ = setup
    grant.state = "draft"
    grant.expires_at = timezone.now() + timedelta(days=181)
    grant.save()
    with pytest.raises(AccessDenied):
        approve_grant(context(ob).request, grant.pk)
    grant.expires_at = timezone.now() + timedelta(days=30)
    grant.save()
    SessionSecurity.objects.filter(account=grant.owner).update(
        password_verified_at=timezone.now() - timedelta(minutes=6)
    )
    with pytest.raises(AccessDenied):
        approve_grant(context(ob).request, grant.pk)


def test_envelope_selection_rejected_after_visibility_epoch_changes(setup):
    from django.db.models import F

    owner, _, _, _, _, db = setup
    item = record(owner)
    callback = context(db).envelope_authorizer(item)
    assert callback(item.identity, "read")
    Account.objects.filter(pk=owner.pk).update(sharing_epoch=F("sharing_epoch") + 1)
    with pytest.raises(AccessDenied):
        callback(item.identity, "read")


def test_selection_and_dependency_bounds(setup):
    owner, _, _, _, _, db = setup
    policy = context(db)
    with pytest.raises(ValueError):
        policy.select([record(owner) for _ in range(129)])
    child = record(owner, "derived_snapshot", dependencies=tuple(record(owner) for _ in range(100)))
    parent = record(owner, "derived_snapshot", dependencies=(child, child))
    with pytest.raises(AccessDenied):
        policy.require(parent)
