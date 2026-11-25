import json
import os
import subprocess

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import SecurityOutbox

ACTIONS = {"record_deleted", "record_private", "grant_revoked", "device_revoked", "account_closed"}


def enqueue(owner_id, action, target_id):
    if action not in ACTIONS:
        raise ValueError("Ledger only accepts permission reductions")
    return SecurityOutbox.objects.create(owner_id=owner_id, action=action, target_id=target_id)


def publish():
    if not settings.HEALTH03_BACKUPS_ENABLED:
        return {"configured": False, "acknowledged": 0, "state": "disabled_by_owner"}
    required = [
        os.environ.get(name)
        for name in ("LEDGER_SSH_DESTINATION", "LEDGER_SSH_KEY", "LEDGER_KNOWN_HOSTS")
    ]
    if not all(required):
        return {"configured": False, "acknowledged": 0}
    destination, identity, hosts = required
    if not destination or destination.startswith("-"):
        raise ValueError("Invalid ledger destination")
    rows = list(SecurityOutbox.objects.filter(acknowledged_at__isnull=True).order_by("id")[:100])
    if not rows:
        return {"configured": True, "acknowledged": 0}
    events = [
        {
            "event_id": str(row.event_id),
            "owner_id": str(row.owner_id),
            "target_id": str(row.target_id),
            "action": row.action,
            "occurred_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
    result = subprocess.run(
        [
            "/usr/bin/ssh",
            "-T",
            "-oBatchMode=yes",
            "-oStrictHostKeyChecking=yes",
            "-oUserKnownHostsFile=" + hosts,
            "-i",
            identity,
            destination,
            "append",
        ],
        input=json.dumps(events).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=True,
    )
    if len(result.stdout) > 65536:
        raise ValueError("Invalid ledger acknowledgement")
    acknowledgements = json.loads(result.stdout)
    if not isinstance(acknowledgements, list) or len(acknowledgements) != len(rows):
        raise ValueError("Incomplete ledger acknowledgement")
    with transaction.atomic():
        for row, ack in zip(rows, acknowledgements, strict=True):
            if (
                ack.get("event_id") != str(row.event_id)
                or type(ack.get("sequence")) is not int
                or ack["sequence"] < 1
                or len(ack.get("hash", "")) != 64
            ):
                raise ValueError("Invalid ledger acknowledgement")
            SecurityOutbox.objects.filter(pk=row.pk, acknowledged_at__isnull=True).update(
                acknowledged_at=timezone.now(),
                remote_sequence=ack["sequence"],
                remote_hash=ack["hash"],
            )
    return {"configured": True, "acknowledged": len(rows)}
