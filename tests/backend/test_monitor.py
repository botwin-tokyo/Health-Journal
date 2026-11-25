import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from accounts.models import Account
from artifacts.models import SecureRecord, SecurityJob
from django.utils import timezone
from jobs.models import Job
from operations.models import BackupSet
from operations.monitor import status


@pytest.mark.django_db
def test_monitor_uses_latest_completion_and_reports_both_queues(settings, tmp_path):
    settings.HEALTH03_BLOB_ROOT = tmp_path / "blobs"
    now = timezone.now()
    owner = Account.objects.create_user("monitor@example.invalid", role="owner")
    blob = SecureRecord.objects.create(owner=owner, ciphertext_bytes=0)
    security = dict(owner=owner, actor=owner, input_record=blob, expires_at=now + timedelta(days=1))
    ordinary = Job.objects.create(reference=uuid.uuid4(), deduplication_key="queued")
    Job.objects.filter(pk=ordinary.pk).update(created_at=now - timedelta(seconds=120))
    Job.objects.create(
        reference=uuid.uuid4(), deduplication_key="expired", state="running", lease_until=now
    )
    SecurityJob.objects.create(**security, state="running", lease_until=now - timedelta(seconds=1))
    SecurityJob.objects.create(**security, state="running", lease_until=now + timedelta(seconds=1))
    with (
        patch("operations.monitor.timezone.now", return_value=now),
        patch("operations.monitor.ssl.create_default_context", side_effect=OSError),
        patch("operations.monitor.subprocess.run"),
    ):
        assert status()["last_complete_backup"] is None
        BackupSet.objects.create(state="complete", finished_at=now - timedelta(days=2))
        assert status()["backup"] == "late"
        recent = now - timedelta(hours=1)
        BackupSet.objects.create(state="complete", finished_at=recent)
        BackupSet.objects.create(state="failed", finished_at=now)
        result = status()
    assert (result["backup"], result["last_complete_backup"]) == ("complete", recent.isoformat())
    assert result["queues"] == {
        "backend": {"queued": 1, "oldest_queued_seconds": 120, "stale_running": 1},
        "security": {"queued": 0, "oldest_queued_seconds": None, "stale_running": 1},
    }
    assert result["stale_jobs"] == 2
