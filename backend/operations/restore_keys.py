"""Explicit isolated key restore. Never targets the primary OpenBao port/storage."""

import json
import os
import ssl
import time
import uuid
from pathlib import Path

import httpx
from artifacts.models import SecureRecord
from crypto.envelopes import EnvelopeService, Identity, TransitKMS


def finish(target, manifest, key_snapshot):
    address = os.environ["RESTORE_KMS_ADDRESS"]
    if address != "https://127.0.0.1:18200":
        raise ValueError("Primary key service is forbidden")
    context = ssl.create_default_context(cafile=os.environ["RESTORE_KMS_CA_FILE"])
    context.load_cert_chain(
        os.environ["RESTORE_KMS_CLIENT_CERT"], os.environ["RESTORE_KMS_CLIENT_KEY"]
    )
    with httpx.Client(base_url=address, verify=context, trust_env=False, timeout=120) as client:
        client.headers["X-Vault-Token"] = (
            Path(os.environ["RESTORE_KMS_INITIAL_TOKEN_FILE"]).read_text().strip()
        )
        with Path(key_snapshot).open("rb") as stream:
            client.post(
                "/v1/sys/storage/raft/snapshot-force",
                content=stream,
                headers={"Content-Type": "application/octet-stream"},
            ).raise_for_status()
        del client.headers["X-Vault-Token"]
        for _ in range(20):
            status = client.get("/v1/sys/seal-status")
            if status.status_code == 200 and status.json()["sealed"]:
                break
            time.sleep(0.5)
        for setting in ("RESTORE_SHARE_1_FILE", "RESTORE_SHARE_2_FILE"):
            client.post(
                "/v1/sys/unseal", json={"key": Path(os.environ[setting]).read_text().strip()}
            ).raise_for_status()
        for _ in range(20):
            if client.get("/v1/sys/health").status_code == 200:
                break
            time.sleep(0.5)
        response = client.post("/v1/auth/cert/login", json={"name": "health03-app"})
        response.raise_for_status()
        client.headers["X-Vault-Token"] = response.json()["auth"]["client_token"]
        kms = TransitKMS()
        kms.close()
        kms.client = client
        service = EnvelopeService(kms)
        canary = manifest["canary"]
        identity = Identity(
            uuid.UUID(canary["owner"]),
            "derived_snapshot",
            uuid.UUID(canary["object"]),
            uuid.UUID(canary["revision"]),
            1,
        )

        def permit_canary(selected, action):
            return selected == identity and action == "read"

        if (
            service.decrypt(canary["envelope"], identity, permit_canary)
            != b"health03 synthetic recovery canary v1"
        ):
            raise ValueError("Restore canary mismatch")
        verified = 0
        for record in SecureRecord.objects.filter(
            deleted_at__isnull=True, purged_at__isnull=True
        ).iterator(chunk_size=128):
            matches = list((target / "blobs").rglob(record.blob_name))
            if len(matches) != 1:
                raise ValueError("Restore record missing")
            expected = Identity(
                record.owner_id, record.kind, record.object_id, record.pk, record.schema_version
            )

            def permit_restore(selected, action):
                return selected == expected and action == "read" and not record.deleted_at

            envelope = json.loads(matches[0].read_bytes())
            plaintext = service.decrypt(envelope, expected, permit_restore)
            del plaintext
            verified += 1
        service.cache.clear()
        client.post("/v1/auth/token/revoke-self", json={}).raise_for_status()
    return verified
