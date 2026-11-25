"""Same-Pi synthetic recovery drill. This is NOT off-device or independent-KMS evidence."""

import hashlib
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "health03_capacity_fixture"
TARGET = "health03_restore_local_rehearsal"
BASE = ROOT / ".local/recovery-rehearsal"


def run(argv, **kwargs):
    return subprocess.run(
        argv, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    )


def main():
    started = time.monotonic()
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    password = BASE / "restic-password"
    if not password.exists():
        descriptor = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(40))
    environment = {
        **os.environ,
        "RESTIC_REPOSITORY": str(BASE / "repository"),
        "RESTIC_PASSWORD_FILE": str(password),
    }
    if not (BASE / "repository").exists():
        run(["restic", "init"], env=environment)
    os.environ["PGDATABASE"] = SOURCE
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["HEALTH03_BLOB_ROOT"] = str(ROOT / ".local/capacity-blobs")
    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    import django

    django.setup()
    import uuid

    from access.models import SharingGrant
    from accounts.models import SessionSecurity
    from artifacts import store
    from artifacts.models import SecureRecord
    from crypto.envelopes import Identity
    from django.conf import settings
    from django.test import Client

    client = Client(HTTP_HOST="api.health03.test")
    response = client.post(
        "/_allauth/browser/v1/auth/login",
        {"email": "capacity@example.invalid", "password": "Synthetic-capacity-only!6912"},
        content_type="application/json",
        secure=True,
        HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
    )
    if response.status_code != 200:
        raise RuntimeError("Synthetic recovery login failed")

    def mutate(path, body, etag=None):
        response = client.post(
            path,
            body,
            content_type="application/json",
            secure=True,
            HTTP_ORIGIN=settings.FRONTEND_ORIGIN,
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            **({"HTTP_IF_MATCH": etag} if etag else {}),
        )
        if response.status_code != 200:
            raise RuntimeError("Synthetic recovery source/report creation failed")
        return response.json()

    weight = mutate(
        "/api/v1/body/weights",
        {"value": "156.2", "unit": "lb", "clinical_date": "2026-11-07", "time_precision": "day"},
    )
    draft = mutate(
        "/api/v1/review/drafts",
        {
            "title": "Synthetic recovery report",
            "clinical_date": "2026-11-07",
            "time_precision": "day",
            "record_ids": [weight["id"]],
        },
    )
    frozen = mutate("/api/v1/review/drafts/" + draft["id"] + "/snapshots", {}, draft["etag"])
    with psycopg.connect(dbname=SOURCE) as connection:
        if connection.execute(
            "SELECT count(*) FROM accounts_account WHERE email <> 'capacity@example.invalid'"
        ).fetchone()[0]:
            raise RuntimeError("Synthetic namespace required")
        target = connection.execute(
            "SELECT id,patient_id FROM records_record WHERE deleted_at IS NULL AND kind='observation' ORDER BY id LIMIT 1"
        ).fetchone()[0]
        owner = connection.execute("SELECT owner_id FROM records_patient LIMIT 1").fetchone()[0]
    dump = subprocess.Popen(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", SOURCE],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        saved = run(
            ["restic", "backup", "--json", "--stdin", "--stdin-filename", "database.dump"],
            env=environment,
            stdin=dump.stdout,
        )
        dump.stdout.close()
        if dump.wait() != 0:
            raise RuntimeError("Database dump failed")
    finally:
        if dump.poll() is None:
            dump.kill()
            dump.wait()
    snapshot = [
        json.loads(line)["snapshot_id"]
        for line in saved.stdout.splitlines()
        if json.loads(line).get("message_type") == "summary"
    ][0]
    blobs = ROOT / ".local/capacity-blobs"
    run(["restic", "backup", "--json", str(blobs)], env=environment)
    with psycopg.connect(dbname="postgres", autocommit=True) as connection:
        if connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", [TARGET]).fetchone():
            raise RuntimeError("Use a new restore namespace; existing candidate retained")
        connection.execute("CREATE DATABASE " + TARGET)
    stream = subprocess.Popen(
        ["restic", "dump", snapshot, "database.dump"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        run(
            ["pg_restore", "--no-owner", "--no-privileges", "--dbname=" + TARGET],
            stdin=stream.stdout,
        )
        stream.stdout.close()
        if stream.wait() != 0:
            raise RuntimeError("Encrypted backup read failed")
    finally:
        if stream.poll() is None:
            stream.kill()
            stream.wait()
    restore_dir = BASE / "restored-ciphertext"
    run(["restic", "restore", "latest", "--target", str(restore_dir)], env=environment)
    os.environ["PGDATABASE"] = TARGET
    from django.db import connections

    connections.close_all()
    settings.DATABASES["default"]["NAME"] = TARGET
    connections["default"].settings_dict["NAME"] = TARGET
    from operations.restore import close_and_replay

    close_and_replay(
        [{"action": "record_deleted", "owner_id": str(owner), "target_id": str(target)}]
    )
    assert not SessionSecurity.objects.exists()
    assert not SharingGrant.objects.filter(state="active").exists()
    assert not SecureRecord.objects.filter(object_id=target, deleted_at=None).exists()
    restored_root = restore_dir / str(blobs).lstrip("/")
    settings.HEALTH03_BLOB_ROOT = restored_root
    count = 0
    for blob in (
        SecureRecord.objects.filter(deleted_at=None)
        .exclude(kind="lab_document")
        .order_by("pk")[:128]
    ):
        identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)

        def authorize(selected, action):
            return selected == identity and action == "read"

        payload = store.read(blob, identity, authorize)
        assert isinstance(json.loads(payload), dict)
        count += 1
    from records.models import Record

    snapshot = Record.objects.select_related("current__blob").get(pk=frozen["id"])
    blob = snapshot.current.blob
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
    content = json.loads(
        store.read(
            blob, identity, lambda selected, action: selected == identity and action == "read"
        )
    )
    assert content["sections"][0]["revision_id"] == weight["revision_id"]
    assert content["sections"][0]["data"]["value"] == "156.2"
    manifest_verified = 0
    for blob in SecureRecord.objects.filter(purged_at=None).iterator(chunk_size=1000):
        path = restored_root / blob.blob_name
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == blob.ciphertext_sha256
        manifest_verified += 1
    report = {
        "synthetic_only": True,
        "same_host": True,
        "independent_key_restore": False,
        "database_restored": True,
        "source_to_report_chain_verified": True,
        "encrypted_blob_hashes_verified": manifest_verified,
        "real_transit_decryptions_verified": count,
        "post_backup_deletion_replayed": True,
        "sessions_revoked": True,
        "doctor_grants_inactive": True,
        "candidate_closed": True,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "off_device_acceptance": False,
    }
    (ROOT / ".local/recovery-rehearsal.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
