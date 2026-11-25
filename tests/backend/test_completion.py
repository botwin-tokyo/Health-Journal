"""Acceptance of completion-pass workflows against real encryption and PostgreSQL."""

import json
import uuid

from test_records import browser as browser_fixture  # noqa: F401
from test_records import mutate
from test_records import pytestmark as pytestmark

browser = browser_fixture


def test_snapshot_and_archive_keep_exact_revisions(browser):
    from jobs.models import Job
    from jobs.service import claim
    from reports.archives import execute
    from reports.models import ExportBundle

    body = {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"}
    weight = mutate(browser, "/api/v1/body/weights", body).json()
    draft = mutate(
        browser,
        "/api/v1/review/drafts",
        {
            "title": "Fictional report",
            "record_ids": [weight["id"]],
            "clinical_date": "2026-11-07",
            "time_precision": "day",
        },
    ).json()
    response = mutate(
        browser, f"/api/v1/review/drafts/{draft['id']}/snapshots", {}, etag=draft["etag"]
    )
    assert response.status_code == 200, response.content
    snapshot = response.json()
    assert snapshot["data"]["sections"][0]["revision_id"] == weight["revision_id"]
    changed = mutate(
        browser,
        f"/api/v1/body/weights/{weight['id']}",
        {**body, "value": "160"},
        method="patch",
        etag=weight["etag"],
    )
    assert changed.status_code == 200, changed.content
    saved = browser.get(f"/api/v1/review/snapshots/{snapshot['id']}", secure=True).json()
    assert saved["data"]["sections"][0]["data"]["value"] == "156.2"
    assert (
        browser.get(f"/api/v1/review/drafts/{draft['id']}", secure=True).json()["outdated"] is True
    )
    response = mutate(browser, "/api/v1/exports", {"format": "body_csv"})
    assert response.status_code == 200, response.content
    Job.objects.exclude(kind="archive").update(state="complete")
    job = claim()
    execute(job)
    bundle = ExportBundle.objects.get(pk=response.json()["id"])
    assert bundle.state == "ready" and bundle.parts.count() == 2
    status = browser.get(f"/api/v1/exports/{bundle.pk}", secure=True).json()
    part = status["parts"][0]["id"]
    ticket = mutate(browser, f"/api/v1/exports/{bundle.pk}/download-tickets", {"part_id": part})
    assert ticket.status_code == 200, ticket.content
    assert ticket.json()["part_id"] == part
    content = browser.get(
        f"/api/v1/exports/{bundle.pk}/content?part_id={part}",
        HTTP_X_DOWNLOAD_TICKET=ticket.json()["ticket"],
        secure=True,
    )
    assert content.status_code == 200
    assert b"160" in b"".join(content.streaming_content)
    replay = browser.get(
        f"/api/v1/exports/{bundle.pk}/content?part_id={part}",
        HTTP_X_DOWNLOAD_TICKET=ticket.json()["ticket"],
        secure=True,
    )
    assert replay.status_code == 404
    from access.policy import JobAuthorizationContext
    from artifacts import store
    from artifacts.selectors import select

    response = mutate(
        browser, "/api/v1/exports", {"format": "owner_archive", "record_ids": [weight["id"]]}
    )
    assert response.status_code == 200, response.content
    bundle = ExportBundle.objects.get(pk=response.json()["id"])
    context = JobAuthorizationContext(bundle.actor_id, bundle.session_hash, None)
    blob, metadata, authorize = select(context, bundle.manifest_id)
    manifest = json.loads(store.read(blob, metadata.identity, authorize))
    assert set(manifest["revisions"]) == {weight["revision_id"], changed.json()["revision_id"]}
    assert manifest["current_revisions"][weight["id"]] == changed.json()["revision_id"]


def test_session_and_contract_routes_are_owned(browser):
    import re
    from pathlib import Path

    from django.urls import resolve

    operations = json.loads(
        (Path(__file__).resolve().parents[2] / "contracts/security/operations.json").read_text()
    )["operations"]
    for operation in operations:
        path = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), operation["path"])
        assert resolve(path).func
    response = browser.get("/api/v1/security/sessions", secure=True)
    assert response.status_code == 200, response.content
    assert sum(row["current"] for row in response.json()["items"]) == 1
    missing = browser.get("/api/v1/account/deletion-requests/" + str(uuid.uuid4()), secure=True)
    assert missing.status_code == 404


def test_settings_windows_and_display_units(browser):
    page = browser.get("/api/v1/settings", secure=True).json()
    invalid = mutate(
        browser,
        "/api/v1/settings",
        {
            "pulmonary_windows": {
                "morning": ["04:00", "12:00"],
                "noon": ["11:00", "16:00"],
                "evening": ["16:00", "24:00"],
            }
        },
        method="patch",
        etag=page["etag"],
    )
    assert invalid.status_code == 422
    body = {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"}
    assert mutate(browser, "/api/v1/body/weights", body).status_code == 200
    response = browser.get("/api/v1/body?date=2026-11-07&weight_unit=lb", secure=True)
    assert response.status_code == 200, response.content
    assert response.json()["items"][0]["data"]["display_value"] == "156.2"


def test_native_versions_conflicts_and_tombstones(browser, monkeypatch):
    from accounts.models import Account
    from ingest.canonical import commit_item
    from ingest.models import SourceConnection
    from jobs.models import Job
    from jobs.service import claim
    from records.models import Record
    from uploader.models import DeviceRegistration

    owner = Account.objects.get(role="owner")
    device = DeviceRegistration.objects.create(owner=owner, label="Fictional contract device")
    source = SourceConnection.objects.create(device=device, namespace=uuid.uuid4())
    Job.objects.create(kind="ingest", reference=uuid.uuid4(), deduplication_key=str(uuid.uuid4()))
    job = claim()
    item = {
        "source_record_id": "stable-native-string",
        "source_revision": 2,
        "kind": "scalar_observation",
        "operation": "upsert",
        "payload": {
            "metric_id": "bpm",
            "value": "68",
            "unit": "beats/min",
            "validity": "valid",
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "source_type": "direct_device",
        },
    }
    accepted, identifier, revision = commit_item(source, item, job)
    assert accepted == "accepted"
    assert commit_item(source, item, job) == ("duplicate", identifier, revision)
    conflict = {**item, "payload": {**item["payload"], "value": "69"}}
    assert commit_item(source, conflict, job)[0] == "conflict"
    # Exercise index migration without rotating the shared deployment's real key.
    from io import StringIO

    from crypto.envelopes import TransitKMS
    from django.core.management import call_command
    from django.test import override_settings
    from ingest.models import SourceLookup

    original_digest = TransitKMS.identity_digest

    def rotated_digest(self, owner_id, kind, identity, namespace, version):
        value = original_digest(self, owner_id, kind, identity, namespace, 1)
        return value if version == 1 else value.replace(":v1:", ":v2:")

    with override_settings(HEALTH03_SOURCE_LOOKUP_VERSIONS=(1, 2)):
        monkeypatch.setattr(TransitKMS, "identity_digest", rotated_digest)
        call_command("reindex_source_lookups", stdout=StringIO())
        assert SourceLookup.objects.filter(identity__record_id=identifier).count() == 2
        assert commit_item(source, item, job) == ("duplicate", identifier, revision)
        assert commit_item(source, {**item, "source_revision": 1}, job)[0] == "superseded"
    monkeypatch.setattr(TransitKMS, "identity_digest", original_digest)
    assert Record.objects.get(pk=identifier).current_id == revision
    assert (
        commit_item(
            source, {**item, "source_revision": 3, "operation": "tombstone", "payload": {}}, job
        )[0]
        == "accepted"
    )
    assert commit_item(source, {**item, "source_revision": 4}, job)[0] == "blocked_deleted"


def test_aggregate_worker_publishes_only_current_lease(browser):
    from jobs.service import claim
    from metrics.aggregates import rebuild
    from metrics.models import AggregateSnapshot
    from records.models import Record

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
    }
    saved = mutate(browser, "/api/v1/body/weights", body)
    assert saved.status_code == 200, saved.content
    job = claim()
    rebuild(job)
    assert (
        AggregateSnapshot.objects.filter(metric="weight", clinical_date="2026-11-07").count() == 2
    )
    response = browser.get("/api/v1/body?date=2026-11-07", secure=True).json()
    assert response["seven_day_mean"]["calculation_state"] == "current"
    from django.db.models import F
    from records.models import Patient

    # A change outside this aggregate's inputs must not leave it perpetually stale.
    Patient.objects.update(source_epoch=F("source_epoch") + 1)
    response = browser.get("/api/v1/body?date=2026-11-07", secure=True).json()
    assert response["seven_day_mean"]["calculation_state"] == "current"
    Patient.objects.update(source_epoch=F("source_epoch") - 1)
    before = AggregateSnapshot.objects.count()
    # A repeated, still-owned job is input-idempotent.
    rebuild(job)
    assert AggregateSnapshot.objects.count() == before
    row = Record.objects.get(pk=saved.json()["id"])
    changed = mutate(
        browser,
        f"/api/v1/body/weights/{row.pk}",
        {
            "value": "157",
            "unit": "lb",
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "representative_action": "keep_corrected",
        },
        method="patch",
        etag=saved.json()["etag"],
    )
    assert changed.status_code == 200, changed.content
    response = browser.get("/api/v1/body?date=2026-11-07", secure=True).json()
    assert response["seven_day_mean"]["calculation_state"] == "updating"


def test_artifact_expired_lease_reclaims_with_new_token(browser):
    from datetime import timedelta

    from accounts.models import Account, SessionSecurity
    from artifacts.jobs import claim
    from artifacts.models import SecurityJob
    from django.utils import timezone
    from records.models import Record

    weight = mutate(
        browser,
        "/api/v1/body/weights",
        {"value": "156", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"},
    ).json()
    owner = Account.objects.get(role="owner")
    blob = Record.objects.get(pk=weight["id"]).current.blob
    old = uuid.uuid4()
    job = SecurityJob.objects.create(
        owner=owner,
        actor=owner,
        session_hash=SessionSecurity.objects.get(account=owner).pk,
        permission_epoch="synthetic-test",
        input_record=blob,
        purpose="render_report",
        state="running",
        lease_id=old,
        lease_until=timezone.now() - timedelta(seconds=1),
        attempts=1,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    reclaimed = claim()
    assert reclaimed.pk == job.pk and reclaimed.lease_id != old and reclaimed.attempts == 2
    SecurityJob.objects.filter(pk=job.pk).update(
        lease_until=timezone.now() - timedelta(seconds=1), attempts=5
    )
    assert claim() is None
    job.refresh_from_db()
    assert job.state == "failed" and job.error_code == "lease_exhausted"


def test_reviewed_lab_publication_and_retry(browser, monkeypatch):
    from artifacts import jobs
    from django.conf import settings
    from labs.models import LabReport, PublishedResult

    token = browser.get("/api/v1/auth/bootstrap", secure=True).json()["csrf_token"]
    uploaded = browser.post(
        "/api/v1/labs/uploads",
        b"%PDF-1.4\nsynthetic-parser-boundary-fixture",
        content_type="application/pdf",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
        HTTP_X_CSRFTOKEN=token,
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )
    assert uploaded.status_code == 202, uploaded.content
    # The actual sandbox/parser has separate text, scan and hostile-file acceptance.
    # This case exercises the encrypted coordinator and publication transaction.
    monkeypatch.setattr(
        jobs,
        "invoke",
        lambda *args: json.dumps(
            {"state": "requires_review", "pages": 1, "text": ["Fictional analyte <5 mg/L"]}
        ).encode(),
    )
    job = jobs.claim()
    jobs.execute(job)
    job.refresh_from_db()
    assert job.state == "ready", job.error_code
    report = LabReport.objects.get(pk=uploaded.json()["id"])
    from labs.views import report_etag

    response = mutate(
        browser,
        f"/api/v1/labs/reports/{report.pk}/review",
        {
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "patient_match_confirmed": True,
            "source_report_status": "final",
            "results": [
                {
                    "label": "Fictional analyte",
                    "raw_result_text": "<5",
                    "value_kind": "numeric",
                    "value": "5",
                    "operator": "lt",
                    "unit": "mg/L",
                }
            ],
        },
        method="patch",
        etag=report_etag(report),
    )
    assert response.status_code == 200, response.content
    key = str(uuid.uuid4())
    published = mutate(
        browser,
        f"/api/v1/labs/reports/{report.pk}/publish",
        {},
        key=key,
        etag=response.json()["etag"],
    )
    assert published.status_code == 200, published.content
    repeated = mutate(
        browser,
        f"/api/v1/labs/reports/{report.pk}/publish",
        {},
        key=key,
        etag=response.json()["etag"],
    )
    assert repeated.json() == published.json() and PublishedResult.objects.count() == 1
    trend = browser.get("/api/v1/labs/trends?from=2026-11-07&to=2026-11-07", secure=True).json()
    point = trend["series"][0]["points"][0]
    assert (
        point["plot_kind"] == "bound"
        and point["data"]["value"] == "5"
        and point["data"]["operator"] == "lt"
    )


def test_rendered_report_download_uses_one_public_route(browser):
    from datetime import timedelta

    from accounts.models import Account
    from artifacts import store
    from artifacts.models import DownloadTicket, SecureRecord, SecurityJob
    from crypto.envelopes import Identity
    from django.urls import get_resolver, resolve
    from django.utils import timezone
    from reports.downloads import content

    owner = Account.objects.get(role="owner")
    blob = SecureRecord(
        owner=owner, kind="report_snapshot", category="journal", mime_type="application/pdf"
    )
    identity = Identity(owner.pk, blob.kind, blob.object_id, blob.pk, 1)
    payload = b"%PDF-synthetic-report" + bytes(128 * 1024)
    blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
        payload, identity, lambda selected, action: selected == identity and action == "write"
    )
    blob.save()
    job = SecurityJob.objects.create(
        owner=owner,
        actor=owner,
        purpose="render_report",
        input_record=blob,
        output_record=blob,
        state="ready",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    url = f"/api/v1/exports/{job.pk}/content"
    assert resolve(url).func is content
    assert (
        sum(pattern.pattern.match(url[1:]) is not None for pattern in get_resolver().url_patterns)
        == 1
    )
    ticket = mutate(browser, f"/api/v1/exports/{job.pk}/download-tickets", {})
    assert ticket.status_code == 200
    headers = {"HTTP_X_DOWNLOAD_TICKET": ticket.json()["ticket"]}
    response = browser.get(url, secure=True, **headers)
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content) == payload
    assert browser.get(url, secure=True, **headers).status_code == 404

    ticket = mutate(browser, f"/api/v1/exports/{job.pk}/download-tickets", {})
    DownloadTicket.objects.filter(consumed_at__isnull=True).update(deadline=timezone.now())
    assert (
        browser.get(url, secure=True, HTTP_X_DOWNLOAD_TICKET=ticket.json()["ticket"]).status_code
        == 404
    )

    ticket = mutate(browser, f"/api/v1/exports/{job.pk}/download-tickets", {})
    response = browser.get(url, secure=True, HTTP_X_DOWNLOAD_TICKET=ticket.json()["ticket"])
    chunks = iter(response.streaming_content)
    assert next(chunks) == payload[:65536]
    SecureRecord.objects.filter(pk=blob.pk).update(deleted_at=timezone.now())
    assert list(chunks) == []
