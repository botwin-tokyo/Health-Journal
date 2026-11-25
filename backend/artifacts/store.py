"""Immutable encrypted blobs. Plaintext is never written to this store."""

import hashlib
import json
import os
import secrets
from pathlib import Path

from crypto.envelopes import EnvelopeService, IntegrityError, TransitKMS
from django.conf import settings

MAX_CIPHERTEXT = 36 * 1024 * 1024


def service():
    # One cache/service per process; incident lock also sets its flag centrally.
    global _service
    if "_service" not in globals():
        _service = EnvelopeService(TransitKMS())
    return _service


def write(plaintext, identity, authorize):
    root = Path(settings.HEALTH03_BLOB_ROOT)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    envelope = service().encrypt(plaintext, identity, authorize)
    encoded = json.dumps(envelope, separators=(",", ":")).encode("ascii")
    name = secrets.token_hex(24) + ".enc"
    temporary = root / ("." + secrets.token_hex(24))
    try:
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            os.fchmod(stream.fileno(), settings.HEALTH03_BLOB_FILE_MODE)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, root / name)  # Atomic publication without replacing another revision.
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    return name, hashlib.sha256(encoded).hexdigest(), len(encoded)


def read(record, identity, authorize):
    if authorize(identity, "read") is not True:
        raise PermissionError("Record unavailable")
    if record.deleted_at or record.purged_at:
        raise PermissionError("Record unavailable")
    path = Path(settings.HEALTH03_BLOB_ROOT) / record.blob_name
    if path.parent != Path(settings.HEALTH03_BLOB_ROOT) or not record.blob_name.endswith(".enc"):
        raise ValueError("Invalid blob reference")
    try:
        with path.open("rb") as stream:
            encoded = stream.read(MAX_CIPHERTEXT + 1)
    except OSError:
        raise IntegrityError("Encrypted object unavailable") from None
    if (
        len(encoded) > MAX_CIPHERTEXT
        or len(encoded) != record.ciphertext_bytes
        or hashlib.sha256(encoded).hexdigest() != record.ciphertext_sha256
    ):
        service().cache.clear()
        raise IntegrityError("Encrypted object integrity failure")
    return service().decrypt(json.loads(encoded), identity, authorize)
