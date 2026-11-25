"""Coherent backup sets. No plaintext database dump is written to disk."""

import hashlib
import json
import os
import ssl
import subprocess
import tempfile
from pathlib import Path

import httpx
from artifacts.models import SecureRecord
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from . import audit
from .models import BackupSet, SecurityOutbox
from .retention import MAINTENANCE_LOCK


def config():
    value = json.loads(Path(os.environ["BACKUP_TARGET_CONFIG"]).read_text())
    if (
        not value.get("repository", "").startswith("rest:https://")
        or value.get("off_device") is not True
    ):
        raise ValueError("Verified off-device TLS rest-server configuration required")
    for key in (
        "password_file",
        "tls_ca_file",
        "kms_ca_file",
        "kms_client_certificate",
        "kms_client_key",
    ):
        if not Path(value[key]).is_file():
            raise ValueError("Missing backup credential material")
    return value


def restic_env(configuration):
    return {
        **os.environ,
        "RESTIC_REPOSITORY": configuration["repository"],
        "RESTIC_PASSWORD_FILE": configuration["password_file"],
        "RESTIC_CACERT": configuration["tls_ca_file"],
    }


def snapshot_id(output):
    for line in reversed(output.splitlines()):
        value = json.loads(line)
        if value.get("message_type") == "summary" and value.get("snapshot_id"):
            return value["snapshot_id"]
    raise RuntimeError("Missing completed restic snapshot")


def save_component(configuration, backup_id, component, arguments, stdin=None):
    result = subprocess.run(
        [
            "restic",
            "backup",
            "--json",
            "--tag",
            "health03-set=" + str(backup_id),
            "--tag",
            "component=" + component,
            *arguments,
        ],
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=restic_env(configuration),
        timeout=7200,
        check=True,
    )
    return snapshot_id(result.stdout)


def perform():
    if not settings.HEALTH03_BACKUPS_ENABLED:
        return {"state": "disabled_by_owner", "backup_created": False}
    configuration = config()
    canary = json.loads(Path(configuration["canary_file"]).read_text())
    backup = BackupSet.objects.create()
    manifest = {
        "version": 1,
        "set_id": str(backup.pk),
        "release_id": os.environ.get("HEALTH03_RELEASE_ID", "development"),
        "started_at": timezone.now().isoformat(),
        "components": {},
        "blobs": [],
        "required_kek_versions": [],
        "canary": canary,
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [MAINTENANCE_LOCK])
    try:
        staging = Path(os.environ.get("BACKUP_STAGING", "/var/lib/health03/backup-staging"))
        staging.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            temporary = Path(temporary)
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    cursor.execute("SELECT pg_export_snapshot()")
                    snapshot = cursor.fetchone()[0]
                rows = list(
                    SecureRecord.objects.filter(purged_at__isnull=True).values(
                        "blob_name", "ciphertext_sha256", "ciphertext_bytes"
                    )
                )
                pending = SecurityOutbox.objects.filter(acknowledged_at__isnull=True).exists()
                if pending:
                    raise RuntimeError("Ledger durability pending")
                manifest["ledger_high_water"] = (
                    SecurityOutbox.objects.aggregate(value=Max("remote_sequence"))["value"] or 0
                )
                latest = SecurityOutbox.objects.filter(
                    remote_sequence=manifest["ledger_high_water"]
                ).first()
                manifest["ledger_hash"] = latest.remote_hash if latest else "0" * 64
                with connection.cursor() as cursor:
                    cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, name")
                    manifest["schema"] = cursor.fetchall()
                database = settings.DATABASES["default"]
                dump = subprocess.Popen(
                    [
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        "--snapshot=" + snapshot,
                        "--host=" + database["HOST"],
                        "--username=" + database["USER"],
                        database["NAME"],
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    result = subprocess.run(
                        [
                            "restic",
                            "backup",
                            "--json",
                            "--stdin",
                            "--stdin-filename",
                            "database.dump",
                            "--tag",
                            "health03-set=" + str(backup.pk),
                            "--tag",
                            "component=database",
                        ],
                        stdin=dump.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        env=restic_env(configuration),
                        timeout=7200,
                    )
                    dump.stdout.close()
                    if result.returncode or dump.wait(timeout=30):
                        raise RuntimeError("Database backup failed")
                    manifest["components"]["database"] = snapshot_id(result.stdout)
                finally:
                    if dump.poll() is None:
                        dump.kill()
                        dump.wait()
                files = []
                versions = set()
                for row in rows:
                    path = Path(settings.HEALTH03_BLOB_ROOT) / row["blob_name"]
                    encoded = path.read_bytes()
                    if (
                        len(encoded) != row["ciphertext_bytes"]
                        or hashlib.sha256(encoded).hexdigest() != row["ciphertext_sha256"]
                    ):
                        raise RuntimeError("Blob manifest mismatch")
                    envelope = json.loads(encoded)
                    versions.add((envelope["key_name"], envelope["key_version"]))
                    files.append(str(path))
                    manifest["blobs"].append(row)
                manifest["required_kek_versions"] = sorted(versions)
                listing = temporary / "blob-paths"
                listing.write_text("\n".join(files) + ("\n" if files else ""))
                if files:
                    manifest["components"]["blobs"] = save_component(
                        configuration, backup.pk, "blobs", ["--files-from", str(listing)]
                    )
                else:
                    manifest["components"]["blobs"] = None
                context = ssl.create_default_context(cafile=configuration["kms_ca_file"])
                context.load_cert_chain(
                    configuration["kms_client_certificate"], configuration["kms_client_key"]
                )
                key_snapshot = temporary / "key-state.snap"
                with httpx.Client(
                    base_url=configuration.get("kms_address", "https://127.0.0.1:8200"),
                    verify=context,
                    trust_env=False,
                    timeout=120,
                ) as kms:
                    login = kms.post("/v1/auth/cert/login", json={"name": "health03-backup"})
                    login.raise_for_status()
                    kms.headers["X-Vault-Token"] = login.json()["auth"]["client_token"]
                    try:
                        with kms.stream("GET", "/v1/sys/storage/raft/snapshot") as response:
                            response.raise_for_status()
                            with key_snapshot.open("xb") as output:
                                for chunk in response.iter_bytes(65536):
                                    output.write(chunk)
                                output.flush()
                                os.fsync(output.fileno())
                    finally:
                        kms.post("/v1/auth/token/revoke-self", json={}).raise_for_status()
                with key_snapshot.open("rb") as key_stream:
                    manifest["key_state_sha256"] = hashlib.file_digest(
                        key_stream, "sha256"
                    ).hexdigest()
                manifest["components"]["keys"] = save_component(
                    configuration, backup.pk, "keys", [str(key_snapshot)]
                )
                manifest["key_state_path"] = str(key_snapshot)
            manifest["completed_at"] = timezone.now().isoformat()
            encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            manifest_snapshot = save_component(
                configuration,
                backup.pk,
                "manifest",
                ["--stdin", "--stdin-filename", "manifest.json"],
                stdin=encoded,
            )
        backup.state, backup.manifest, backup.manifest_snapshot = (
            "complete",
            manifest,
            manifest_snapshot,
        )
        backup.finished_at = timezone.now()
        backup.save()
        audit.emit("backup_complete", target=backup.pk)
        return {"set_id": str(backup.pk), "state": "complete"}
    except Exception:
        BackupSet.objects.filter(pk=backup.pk).update(
            state="failed", error_code="backup_component_failed", finished_at=timezone.now()
        )
        audit.emit("backup_failed", target=backup.pk, outcome="failed")
        raise RuntimeError("Backup failed; set is not recoverable/complete") from None
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [MAINTENANCE_LOCK])
