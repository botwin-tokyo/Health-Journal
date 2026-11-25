import shutil
import ssl
import subprocess
from datetime import timedelta
from pathlib import Path

import httpx
from artifacts.models import SecurityJob
from django.conf import settings
from django.db.models import Count, Min, Q
from django.utils import timezone
from jobs.models import Job

from .models import BackupSet, SecurityOutbox


def queue_status(model, now):
    counts = model.objects.aggregate(
        queued=Count("pk", filter=Q(state="queued")),
        oldest=Min("created_at", filter=Q(state="queued")),
        stale=Count("pk", filter=Q(state="running", lease_until__lte=now)),
    )
    oldest = counts["oldest"]
    return {
        "queued": counts["queued"],
        "oldest_queued_seconds": max(0, int((now - oldest).total_seconds())) if oldest else None,
        "stale_running": counts["stale"],
    }


def status():
    now = timezone.now()
    backup = (
        BackupSet.objects.filter(state="complete", finished_at__isnull=False)
        .order_by("-finished_at")
        .first()
    )
    queues = {"backend": queue_status(Job, now), "security": queue_status(SecurityJob, now)}
    result = {
        "backup": "not_configured"
        if not backup
        else "late"
        if now - backup.finished_at > timedelta(hours=24)
        else "complete",
        "last_complete_backup": backup.finished_at.isoformat() if backup else None,
        "ledger_pending": SecurityOutbox.objects.filter(acknowledged_at__isnull=True).count(),
        "stale_jobs": sum(queue["stale_running"] for queue in queues.values()),
        "queues": queues,
        "restore": "not_verified",
    }
    usage = shutil.disk_usage(Path(settings.HEALTH03_BLOB_ROOT).parent)
    result["disk_free_fraction"] = round(usage.free / usage.total, 3)
    try:
        context = ssl.create_default_context(cafile="/etc/health03/bao-server-ca.crt")
        with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
            response = client.get("https://127.0.0.1:8200/v1/sys/health")
            result["kms"] = (
                "available"
                if response.status_code == 200 and not response.json()["sealed"]
                else "unavailable"
            )
    except Exception:
        result["kms"] = "unavailable"
    result["certificates"] = {}
    for name, path in [
        ("server", "/etc/health03/openbao/server.crt"),
        ("app", "/etc/health03/bao-agent/client.crt"),
    ]:
        check = subprocess.run(
            ["openssl", "x509", "-checkend", str(30 * 86400), "-noout", "-in", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        result["certificates"][name] = (
            "valid_over_30_days" if check.returncode == 0 else "renewal_or_inspection_required"
        )
    return result
