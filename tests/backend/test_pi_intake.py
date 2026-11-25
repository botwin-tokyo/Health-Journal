"""Synthetic receipt, rollback, concurrent retry and historical index checks on PostgreSQL/Transit."""

import copy
import hashlib
import json
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from accounts.models import Account
from allauth.account.models import EmailAddress
from artifacts.models import SecureRecord
from django.core.management import call_command
from django.db import connections
from django.test import Client
from ingest import blood_pressure_backfill, views
from ingest.models import IngestBatch, SourceAsset, SourceConnection
from jobs.models import Job
from records.models import Record
from test_records import pytestmark as pytestmark
from uploader.models import DeviceAPIKey, DeviceRegistration


@pytest.fixture
def intake(settings, tmp_path):
    settings.HEALTH03_BLOB_ROOT = tmp_path
    owner = Account.objects.create_user(
        "phone@example.invalid", role="owner", enrollment_complete=True
    )
    EmailAddress.objects.create(user=owner, email=owner.email, verified=True)
    return registered_phone(owner)


def registered_phone(owner):
    device = DeviceRegistration.objects.create(owner=owner, label="Synthetic phone")
    source = SourceConnection.objects.create(device=device, namespace=uuid.uuid4())
    key = "h03_" + secrets.token_hex(32)
    DeviceAPIKey.objects.create(device=device, digest=hashlib.sha256(key.encode()).hexdigest())
    phone = Client(HTTP_HOST="api.health03.test", HTTP_X_API_KEY=key)
    batch = json.loads(
        (Path(__file__).parents[2] / "contracts/phone/sample-batch.json").read_text()
    )
    batch.update(batch_id=str(uuid.uuid4()), source_namespace=str(source.namespace))
    return phone, batch


def submit(phone, batch, asset):
    if asset:
        return phone.post(
            "/api/v1/ingestion/assets",
            b"test asset",
            content_type="application/octet-stream",
            secure=True,
            HTTP_X_SOURCE_NAMESPACE=batch["source_namespace"],
            HTTP_X_SOURCE_RECORD_ID="fixture:asset",
            HTTP_X_SOURCE_KIND="source_record",
        )
    return phone.post(
        "/api/v1/ingestion/batches", batch, content_type="application/json", secure=True
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("asset", "different_devices", "expected"),
    [(False, False, [200, 202]), (True, False, [200, 200]), (False, True, [202, 409])],
)
def test_concurrent_retries_publish_one_blob(
    intake, tmp_path, monkeypatch, asset, different_devices, expected
):
    phone, batch = intake
    other_phone, other_batch = (
        registered_phone(Account.objects.get()) if different_devices else intake
    )
    other_batch["batch_id"] = batch["batch_id"]
    both_checked = threading.Barrier(2)
    original = views.intake_transaction

    @contextmanager
    def concurrent(evidence):
        both_checked.wait(timeout=10)
        with original(evidence):
            yield

    monkeypatch.setattr(views, "intake_transaction", concurrent)

    def retry(args):
        client, body = args
        try:
            return submit(Client(**client.defaults), body, asset).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(retry, [(phone, batch), (other_phone, other_batch)]))
    assert statuses == expected
    assert SecureRecord.objects.count() == 1
    assert [p.name for p in tmp_path.iterdir()] == [SecureRecord.objects.get().blob_name]


@pytest.mark.parametrize("asset", [False, True])
def test_database_failure_cleans_ciphertext(intake, tmp_path, monkeypatch, asset):
    def fail(*args, **kwargs):
        raise RuntimeError("injected rollback")

    if asset:
        monkeypatch.setattr(SourceAsset.objects, "create", fail)
    else:
        monkeypatch.setattr(views, "enqueue", fail)
    with pytest.raises(RuntimeError, match="injected rollback"):
        submit(*intake, asset=asset)
    assert not list(tmp_path.iterdir())
    assert not SecureRecord.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_worker_repairs_only_current_pressure_and_resumes_after_restart(intake):
    phone, batch = intake
    sample = json.loads((Path(__file__).parents[2] / "contracts/phone/fixtures.json").read_text())[
        0
    ]["item"]
    sample["payload"].update(
        metric_id="blood_pressure_systolic",
        value="118",
        unit="mmHg",
        timestamp_basis="measurement",
        measurement_time_verified=True,
    )
    items = [
        dict(copy.deepcopy(sample), source_record_id=key)
        for key in ("current", "corrected", "deleted")
    ]

    def process(items):
        batch.update(batch_id=str(uuid.uuid4()), items=items)
        assert submit(phone, batch, False).status_code == 202
        for _ in range(20):
            call_command("run_backend_worker", once=True)
            if IngestBatch.objects.filter(pk=batch["batch_id"], state="processed").exists():
                break
        receipts = phone.get(f"/api/v1/ingestion/batches/{batch['batch_id']}", secure=True).json()
        assert receipts["state"] == "processed"
        assert all(row["outcome"] == "accepted" for row in receipts["items"]), receipts
        return receipts["items"]

    original = process(items)
    revised = copy.deepcopy(items[1])
    revised["source_revision"] = 2
    revised["payload"]["value"] = "121"
    deleted = dict(items[2], source_revision=2, operation="tombstone", payload={})
    # Preserve the historical record kind of the pre-upgrade system.
    Record.objects.filter(pk__in=[r["record_id"] for r in original]).update(kind="observation")
    first_batch = batch["batch_id"]
    # Keep this historical batch out of the worker until the newer operations commit.
    prior = IngestBatch.objects.get(pk=first_batch)
    prior.state = "received"
    prior.save(update_fields=["state"])
    process([revised, deleted])
    prior.state = "processed"
    prior.save(update_fields=["state"])
    for _ in range(20):
        call_command("run_backend_worker", once=True)
        if Job.objects.filter(
            kind=blood_pressure_backfill.KIND, reference=first_batch, state="complete"
        ).exists():
            break
    assert Job.objects.filter(
        kind=blood_pressure_backfill.KIND, reference=first_batch, state="complete"
    ).exists()
    current, corrected, removed = [Record.objects.get(pk=r["record_id"]) for r in original]
    assert (
        current.kind == "blood_pressure" and str(current.current_id) == original[0]["revision_id"]
    )
    assert str(corrected.current_id) != original[1]["revision_id"]
    assert removed.deleted_at is not None
    call_command("run_backend_worker", once=True)
    assert Job.objects.filter(kind=blood_pressure_backfill.KIND, reference=first_batch).count() == 1


@pytest.mark.django_db(transaction=True)
def test_phone_handshake_matches_published_contract(intake):
    from jsonschema import Draft202012Validator

    phone, batch = intake
    spec = json.loads((Path(__file__).parents[2] / "contracts/openapi.yaml").read_text())
    path = "/api/v1/ingestion/batches"
    post = spec["paths"][path]["post"]
    get = spec["paths"][path + "/{batch_id}"]["get"]

    def check(response, operation, expected):
        assert response.status_code == expected
        declared = operation["responses"][str(expected)]["content"]["application/json"]["schema"]
        Draft202012Validator({**declared, "components": spec["components"]}).validate(
            response.json()
        )
        return response.json()

    assert {"DeviceApiKey": []} in post["security"] and {"UploaderBearer": []} in post["security"]
    request_schema = post["requestBody"]["content"]["application/json"]["schema"]
    Draft202012Validator({**request_schema, "components": spec["components"]}).validate(batch)
    first = check(submit(phone, batch, False), post, 202)
    replay = check(submit(phone, batch, False), post, 200)
    assert first == replay
    assert check(phone.get(first["receipt_url"], secure=True), get, 200)["items"] == []
    changed = {**batch, "generated_at": "2020-01-01T00:00:00Z"}
    assert check(submit(phone, changed, False), post, 409)["error"]["code"] == "batch_conflict"
    call_command("run_backend_worker", once=True)
    status = check(phone.get(first["receipt_url"], secure=True), get, 200)
    assert len(status["items"]) == len(batch["items"])
