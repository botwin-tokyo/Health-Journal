import json
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from ingest import blood_pressure_backfill as repair
from records.validation import DomainError


def test_scheduler_is_bounded_and_excludes_durable_jobs(monkeypatch):
    jobs, batches, enqueue = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(repair.Job, "objects", jobs)
    monkeypatch.setattr(repair.IngestBatch, "objects", batches)
    monkeypatch.setattr(repair, "enqueue", enqueue)
    pending = batches.filter.return_value.exclude.return_value.order_by.return_value.values_list.return_value
    pending.__getitem__.return_value = ["batch-a", "batch-b"]
    repair.schedule()
    jobs.filter.assert_called_once_with(kind=repair.KIND)
    batches.filter.return_value.exclude.assert_called_once_with(
        pk__in=jobs.filter.return_value.values.return_value
    )
    pending.__getitem__.assert_called_once_with(slice(None, 16, None))
    assert enqueue.call_args_list[0].args == (repair.KIND, "batch-a", 1)
    assert enqueue.call_count == 2


def setup_job(monkeypatch, current=True, valid_lease=True):
    job = SimpleNamespace(pk="job", reference="batch", lease_token="token")
    receipt = MagicMock(ordinal=0, record_id="record", revision_id="revision")
    blob = SimpleNamespace(owner_id="owner", kind="kind", object_id="object", pk="blob")
    batch = MagicMock(evidence=blob)
    batch.receipts.filter.return_value = [receipt]
    batches, jobs, records, secure, versions = [MagicMock() for _ in range(5)]
    for model, manager in [
        (repair.IngestBatch, batches),
        (repair.Job, jobs),
        (repair.Record, records),
        (repair.SecureRecord, secure),
        (repair.SourceVersion, versions),
    ]:
        monkeypatch.setattr(model, "objects", manager)
    batches.select_related.return_value.filter.return_value.first.return_value = batch
    jobs.select_for_update.return_value.get.return_value = SimpleNamespace(
        state="running",
        lease_token="token" if valid_lease else "expired",
        lease_until=timezone.now() + timedelta(minutes=1),
    )
    record = MagicMock()
    records.select_for_update.return_value.filter.return_value.select_related.return_value.first.return_value = (
        record if current else None
    )
    monkeypatch.setattr(repair.transaction, "atomic", nullcontext)
    monkeypatch.setattr(repair, "authorizer", lambda *args: None)
    monkeypatch.setattr(repair, "Identity", lambda *args: None)
    monkeypatch.setattr(
        repair.store,
        "read",
        lambda *args: json.dumps(
            {
                "items": [
                    {
                        "operation": "upsert",
                        "kind": "scalar_observation",
                        "payload": {"metric_id": "blood_pressure_systolic"},
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        repair,
        "normalize",
        lambda item: (
            "blood_pressure",
            "sleep_activity",
            "2020-01-02",
            {"clinical_eligible": False, "record_status": "evidence"},
        ),
    )
    return job, records, record, secure, versions


def test_only_current_live_record_is_reindexed_without_rewriting_evidence(monkeypatch):
    job, records, record, secure, versions = setup_job(monkeypatch)
    repair.execute(job)
    records.select_for_update.return_value.filter.assert_called_once_with(
        pk="record",
        current_id="revision",
        kind="observation",
        deleted_at__isnull=True,
        superseded_at__isnull=True,
    )
    assert record.kind == "blood_pressure"
    record.save.assert_called_once_with(update_fields=["kind"])
    secure.filter.return_value.update.assert_called_once_with(
        category="sleep_activity",
        clinical_date="2020-01-02",
        owner_only=True,
    )
    versions.filter.assert_called_once_with(revision_id="revision")


def test_newer_or_deleted_record_is_untouched(monkeypatch):
    job, _, record, secure, versions = setup_job(monkeypatch, current=False)
    repair.execute(job)
    record.save.assert_not_called()
    secure.filter.assert_not_called()
    versions.filter.assert_not_called()


def test_expired_lease_cannot_publish(monkeypatch):
    job, records, _, secure, _ = setup_job(monkeypatch, valid_lease=False)
    with pytest.raises(DomainError, match="lease_lost"):
        repair.execute(job)
    records.select_for_update.assert_not_called()
    secure.filter.assert_not_called()
