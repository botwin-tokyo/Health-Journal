"""Fail-closed restore candidate preparation and ledger replay."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from access.models import SharingGrant
from accounts.models import Account, Invitation, SessionSecurity
from artifacts.models import DownloadTicket, SecureRecord, SecurityJob
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection, transaction
from django.utils import timezone
from uploader.models import DeviceRegistration
from uploader.policy import revoke_account_families

from .models import OperationalControl


def verify_ledger(path, required_sequence, required_hash):
    previous, sequence = "0" * 64, 0
    events = []
    with Path(path).open() as source:
        for line in source:
            if len(line) > 4096:
                raise ValueError("Ledger record too large")
            row = json.loads(line)
            sequence += 1
            if row["sequence"] != sequence or row["previous_hash"] != previous:
                raise ValueError("Ledger gap")
            canonical = json.dumps(row["event"], sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256((previous + canonical).encode()).hexdigest()
            if row["hash"] != digest:
                raise ValueError("Ledger integrity failure")
            if sequence == required_sequence and digest != required_hash:
                raise ValueError("Ledger high-water mismatch")
            previous = digest
            events.append(row["event"])
    if sequence < required_sequence:
        raise ValueError("Ledger incomplete")
    # Operator-provided fresh head is required; a truncated but internally valid chain is insufficient.
    expected = json.loads(Path(os.environ["RESTORE_LEDGER_HEAD"]).read_text())
    if expected != {"sequence": sequence, "hash": previous}:
        raise ValueError("Current independent ledger head missing/mismatched")
    return events


@transaction.atomic
def close_and_replay(events):
    OperationalControl.objects.update_or_create(
        pk=1, defaults={"incident_locked": True, "restored_candidate": True}
    )
    SessionSecurity.objects.all().delete()
    Session.objects.all().delete()
    Invitation.objects.all().delete()
    DownloadTicket.objects.all().delete()
    for account in Account.objects.all():
        revoke_account_families(account)
    DeviceRegistration.objects.all().update(revoked_at=timezone.now())
    SharingGrant.objects.all().update(state="revoked", revoked_at=timezone.now())
    SecurityJob.objects.all().update(state="cancelled", error_code="restored_candidate")
    from ingest.models import SourceConnection
    from reports.models import ExportBundle

    ExportBundle.objects.all().update(state="revoked", error_code="restored_candidate")
    SourceConnection.objects.all().update(disabled_at=timezone.now())
    now = timezone.now()
    for event in events:
        owner, target = event["owner_id"], event["target_id"]
        if event["action"] == "account_closed":
            Account.objects.filter(pk=owner).update(is_active=False)
            SecureRecord.objects.filter(owner_id=owner).update(deleted_at=now, purge_after=now)
        elif event["action"] == "record_deleted":
            from ingest.models import SourceIdentity, SourceTombstone
            from records.models import Record

            Record.objects.filter(pk=target, patient__owner_id=owner).update(deleted_at=now)
            for identity in SourceIdentity.objects.filter(
                record_id=target, record__patient__owner_id=owner
            ):
                SourceTombstone.objects.get_or_create(
                    source=identity.source,
                    identity_digest=identity.digest,
                    lookup_version=identity.lookup_version,
                )
            ids = set(
                SecureRecord.objects.filter(owner_id=owner, object_id=target).values_list(
                    "pk", flat=True
                )
            )
            frontier = ids.copy()
            while frontier:
                frontier = (
                    set(
                        SecureRecord.objects.filter(dependencies__pk__in=frontier).values_list(
                            "pk", flat=True
                        )
                    )
                    - ids
                )
                ids.update(frontier)
            SecureRecord.objects.filter(pk__in=ids).update(deleted_at=now, purge_after=now)
        elif event["action"] == "record_private":
            SecureRecord.objects.filter(owner_id=owner, object_id=target).update(
                visibility="private"
            )
        elif event["action"] not in {"grant_revoked", "device_revoked"}:
            raise ValueError("Unsupported ledger action")


def restore(manifest_snapshot):
    if settings.ENVIRONMENT != "restore" or not settings.DATABASES["default"]["NAME"].startswith(
        "health03_restore_"
    ):
        raise ValueError("Restore refuses the primary environment/database")
    target = Path(os.environ["RESTORE_DIRECTORY"]).resolve()
    if not str(target).startswith("/var/lib/health03-restore/") or target.exists():
        raise ValueError("Restore requires a new isolated candidate directory")
    if os.environ.get("RESTORE_KMS_ADDRESS") != "https://127.0.0.1:18200":
        raise ValueError("Restore requires the isolated key-service listener")
    from .backup import config, restic_env

    configuration = config()
    environment = restic_env(configuration)
    started = time.monotonic()
    import uuid

    set_id = str(uuid.UUID(manifest_snapshot))
    catalog = subprocess.run(
        ["restic", "snapshots", "--json", "--tag", "health03-set=" + set_id],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=True,
    )
    candidates = [
        item for item in json.loads(catalog.stdout) if "component=manifest" in item.get("tags", [])
    ]
    if len(candidates) != 1:
        raise ValueError("Backup set has no unique completion manifest")
    manifest_snapshot = candidates[0]["id"]
    result = subprocess.run(
        ["restic", "dump", manifest_snapshot, "manifest.json"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=True,
    )
    manifest = json.loads(result.stdout)
    if manifest.get("version") != 1 or not manifest.get("completed_at"):
        raise ValueError("Incomplete backup set")
    events = verify_ledger(
        os.environ["RESTORE_LEDGER_EXPORT"], manifest["ledger_high_water"], manifest["ledger_hash"]
    )
    target.mkdir(mode=0o700, parents=True)
    # Never launch a web/tunnel service in this environment.
    connection.close()
    source = subprocess.Popen(
        ["restic", "dump", manifest["components"]["database"], "database.dump"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    try:
        restored = subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--host=" + (settings.DATABASES["default"].get("HOST") or "/var/run/postgresql"),
                "--username=" + settings.DATABASES["default"]["USER"],
                "--dbname=" + settings.DATABASES["default"]["NAME"],
            ],
            stdin=source.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3600,
        )
        source.stdout.close()
        if restored.returncode or source.wait(timeout=30):
            raise RuntimeError("Restore database failed")
    finally:
        if source.poll() is None:
            source.kill()
            source.wait()
    close_and_replay(events)
    for component in ("blobs", "keys"):
        snapshot = manifest["components"][component]
        if snapshot:
            subprocess.run(
                ["restic", "restore", snapshot, "--target", str(target / component)],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3600,
                check=True,
            )
    for blob in manifest["blobs"]:
        matches = list((target / "blobs").rglob(blob["blob_name"]))
        if len(matches) != 1 or matches[0].stat().st_size != blob["ciphertext_bytes"]:
            raise ValueError("Restored blob missing")
        with matches[0].open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != blob["ciphertext_sha256"]:
                raise ValueError("Restored blob mismatch")
    keys = list((target / "keys").rglob("key-state.snap"))
    if len(keys) != 1:
        raise ValueError("Restored key snapshot missing")
    with keys[0].open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["key_state_sha256"]:
            raise ValueError("Restored key snapshot mismatch")
    from .restore_keys import finish

    verified = finish(target, manifest, keys[0])
    from datetime import datetime

    rpo = (timezone.now() - datetime.fromisoformat(manifest["started_at"])).total_seconds()
    elapsed = round(time.monotonic() - started)
    report = {
        "state": "verified_closed_candidate",
        "set_id": manifest["set_id"],
        "elapsed_seconds": elapsed,
        "rpo_seconds": rpo,
        "targets_met": elapsed <= 14400 and rpo <= 86400,
        "database_and_blob_hashes_verified": True,
        "decryption_verified": True,
        "verified_envelopes": verified,
        "restored_sessions_revoked": True,
        "grants_inactive": True,
    }
    (target / "restore-evidence.json").write_text(json.dumps(report, indent=2))
    return report
