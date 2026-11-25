"""Full wire intake/receipts/display with real local encryption; synthetic isolated database."""

import copy
import hashlib
import json
import secrets
import uuid
from pathlib import Path

from django.test import Client
from ingest.models import IngestBatch, SourceConnection
from ingest.service import process
from jobs.models import Job
from jobs.service import claim, finish
from records.models import Record
from test_records import browser as browser_fixture
from test_records import pytestmark as pytestmark
from uploader.models import DeviceAPIKey, DeviceRegistration

browser = browser_fixture
FIXTURES = json.loads((Path(__file__).parents[2] / "contracts/phone/fixtures.json").read_text())


def test_contract_intake_receipts_render_replay_revision_delete_assets(browser):
    from accounts.models import Account

    owner = Account.objects.get(email="backend-owner@example.invalid")
    device = DeviceRegistration.objects.create(owner=owner, label="Synthetic contract phone")
    source = SourceConnection.objects.create(device=device, namespace=uuid.uuid4())
    key = "h03_" + secrets.token_hex(32)
    DeviceAPIKey.objects.create(device=device, digest=hashlib.sha256(key.encode()).hexdigest())
    phone = Client(HTTP_HOST="api.health03.test", HTTP_X_API_KEY=key)
    assert phone.get("/api/v1/ingestion/config", secure=True).status_code == 200
    cases = copy.deepcopy(FIXTURES)
    # Asset is associated with the parent session's immutable source identity, including nested links.
    asset = phone.post(
        "/api/v1/ingestion/assets",
        b'{"source":"DIRECT_RING","stageAlgorithm":"phone-native"}',
        content_type="application/octet-stream",
        secure=True,
        HTTP_X_SOURCE_NAMESPACE=str(source.namespace),
        HTTP_X_SOURCE_RECORD_ID="fixture:sleep_stages",
        HTTP_X_SOURCE_KIND="sleep_session",
    )
    assert asset.status_code == 200, asset.content
    asset_id = asset.json()["id"]
    next(case for case in cases if case["name"] == "sleep_stages")["item"]["payload"][
        "asset_ids"
    ] = [asset_id]

    sleep_payload = next(case for case in cases if case["name"] == "sleep_stages")["item"][
        "payload"
    ]
    native_bytes = b'{"source":"DIRECT_RING","stageAlgorithm":"phone-native"}'
    sleep_payload["native_record_assets"] = {
        "encoding": "concatenated-utf8-json-v1",
        "ids": [asset_id],
        "bytes": len(native_bytes),
        "sha256": hashlib.sha256(native_bytes).hexdigest(),
    }
    sleep_payload["source_type"] = "direct_ring"

    def upload(items):
        payload = {
            "schema_version": "pb-health-export-1",
            "canonicalization": "jcs-rfc8785-v1",
            "batch_id": str(uuid.uuid4()),
            "source_namespace": str(source.namespace),
            "generated_at": "2020-01-02T12:00:00Z",
            "items": items,
        }
        response = phone.post(
            "/api/v1/ingestion/batches", payload, content_type="application/json", secure=True
        )
        assert response.status_code == 202, response.content
        # Keep unrelated derived recalculations separate from the ingestion job under test.
        Job.objects.filter(kind="invalidate").update(state="complete")
        job = claim()
        assert job.kind == "ingest"
        process(job)
        finish(job)
        receipt = phone.get(response.json()["receipt_url"], secure=True)
        assert receipt.status_code == 200, receipt.content
        return payload, receipt.json()

    payload, receipt = upload([case["item"] for case in cases])
    assert receipt["state"] == "processed"
    for case, result in zip(cases, receipt["items"]):
        expected = case["expected"]
        assert (result["outcome"], result["disposition"]) == (
            expected["outcome"],
            expected["disposition"],
        ), (case["name"], result)
        if expected["outcome"] == "rejected":
            assert result["reason"] == expected["reason"]
    before = Record.objects.count()
    repeat = phone.post(
        "/api/v1/ingestion/batches", payload, content_type="application/json", secure=True
    )
    assert repeat.status_code == 200 and Record.objects.count() == before
    same_items = upload(
        [case["item"] for case in cases if case["expected"]["outcome"] == "accepted"]
    )[1]
    assert all(row["outcome"] == "duplicate" for row in same_items["items"])
    assert Record.objects.count() == before
    body = browser.get("/api/v1/body?date=2020-01-02&weight_unit=kg", secure=True)
    assert body.status_code == 200, body.content
    assert body.json()["representative_record"]["data"]["canonical_value"] == "70.25"
    sleep = browser.get("/api/v1/sleep-activity?date=2020-01-02", secure=True)
    assert sleep.status_code == 200, sleep.content
    assert sleep.json()["sleep"]["stage_summary"]["known_sleep_seconds"] == 25200
    assert any(row["display_status"] == "Partial session" for row in sleep.json()["sleep_sessions"])
    assert any(row["data"].get("clinical_eligible") is False for row in sleep.json()["sleep_sessions"])
    breathing = browser.get("/api/v1/breathing?date=2020-01-02&slot=morning", secure=True)
    assert breathing.status_code == 200, breathing.content
    assert breathing.json()["selected_session"]["data"]["values"]["fev1"] == "2.9"
    assert len(breathing.json()["selected_session"]["data"]["trials"]) == 2
    assert any(
        row["daily_duration"]["value"] == "540.0" or row["daily_duration"]["value"] == "540"
        for row in sleep.json()["workouts"]
    )
    phone_body = browser.get(
        "/api/v1/phone/records?domain=body&from=2020-01-02&to=2020-01-02", secure=True
    )
    assert phone_body.status_code == 200, phone_body.content
    assert any(row["data"].get("metric_id") == "bmi" for row in phone_body.json()["items"])
    assert any(row["kind"] == "body_context" for row in phone_body.json()["items"])
    sleep_record = receipt["items"][
        next(i for i, c in enumerate(cases) if c["name"] == "sleep_stages")
    ]["record_id"]
    evidence_url = f"/api/v1/phone/records/{sleep_record}/assets/{asset_id}"
    content = browser.get(evidence_url, secure=True)
    assert content.status_code == 200 and content.content == native_bytes
    assert phone.get(evidence_url, secure=True).status_code in {401, 403, 404}
    weight = copy.deepcopy(cases[0]["item"])
    weight["source_revision"] = 2
    weight["payload"]["value"] = "71"
    revised = upload([weight])[1]["items"][0]
    assert revised["outcome"] == "accepted" and Record.objects.count() == before
    changed = browser.get("/api/v1/body?date=2020-01-02&weight_unit=kg", secure=True)
    assert changed.json()["representative_record"]["data"]["canonical_value"] == "71"
    tombstone = copy.deepcopy(next(c["item"] for c in cases if c["name"] == "sleep_stages"))
    tombstone.update(source_revision=2, operation="tombstone", payload={})
    deleted = upload([tombstone])[1]["items"][0]
    assert deleted["outcome"] == "accepted" and deleted["disposition"] == "deleted"
    assert browser.get(evidence_url, secure=True).status_code == 404
    resurrect = copy.deepcopy(next(c["item"] for c in cases if c["name"] == "sleep_stages"))
    resurrect["source_revision"] = 3
    assert upload([resurrect])[1]["items"][0]["outcome"] == "blocked_deleted"
    assert IngestBatch.objects.count() == 5
