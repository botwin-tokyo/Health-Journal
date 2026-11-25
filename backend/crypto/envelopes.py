"""Clinical envelopes. Callers must supply the current record authorization policy.

No built-in key, plaintext fallback, or standalone health endpoint is provided.
Python key/reference cleanup is best effort, not a zeroization guarantee.
"""

import base64
import binascii
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KINDS = frozenset(
    {
        "clinical_record",
        "journal_entry",
        "lab_document",
        "report_snapshot",
        "profile_revision",
        "source_identity",
        "derived_snapshot",
        "appointment_question",
        "medication_event",
    }
)
MAX_PAYLOAD = 25 * 1024 * 1024
FIELDS = {
    "envelope_version",
    "algorithm",
    "key_name",
    "key_version",
    "wrapped_dek",
    "nonce",
    "ciphertext",
    "payload_schema_version",
}
log = logging.getLogger("health03.security")


class IntegrityError(Exception):
    pass


class KMSUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    owner_id: uuid.UUID
    kind: str
    object_id: uuid.UUID
    revision_id: uuid.UUID
    schema_version: int

    def aad(self):
        if (
            self.kind not in KINDS
            or type(self.schema_version) is not int
            or self.schema_version < 1
        ):
            raise IntegrityError("Invalid encrypted object")
        if not all(
            isinstance(value, uuid.UUID)
            for value in (self.owner_id, self.object_id, self.revision_id)
        ):
            raise IntegrityError("Invalid encrypted object")
        return json.dumps(
            [
                1,
                str(self.owner_id),
                self.kind,
                str(self.object_id),
                str(self.revision_id),
                self.schema_version,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")


class TransitKMS:
    def __init__(self, socket="/run/health03-bao-agent/api.sock"):
        self.client = httpx.Client(
            transport=httpx.HTTPTransport(uds=socket),
            base_url="http://localhost",
            timeout=5,
            trust_env=False,
        )

    def close(self):
        self.client.close()

    def _post(self, path, payload, field):
        try:
            response = self.client.post("/v1/transit/" + path, json=payload)
            response.raise_for_status()
            value = response.json()["data"][field]
            if not isinstance(value, str) or not 1 <= len(value) <= 2048:
                raise ValueError
            return value
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise KMSUnavailable("Key service unavailable") from None

    def wrap(self, key):
        return self._post(
            "encrypt/clinical-dek",
            {"plaintext": base64.b64encode(key).decode("ascii")},
            "ciphertext",
        )

    def unwrap(self, wrapped):
        try:
            key = base64.b64decode(
                self._post("decrypt/clinical-dek", {"ciphertext": wrapped}, "plaintext"),
                validate=True,
            )
            if len(key) != 32:
                raise ValueError
            return key
        except (KeyError, ValueError, binascii.Error):
            raise KMSUnavailable("Key service unavailable") from None

    def identity_digest(self, owner_id, source, source_record_id, namespace, version):
        if not isinstance(owner_id, uuid.UUID) or type(version) is not int or version < 1:
            raise ValueError("Invalid lookup identity")
        if not all(
            isinstance(value, str) and 0 < len(value) <= 1024
            for value in (source, source_record_id, namespace)
        ):
            raise ValueError("Invalid lookup identity")
        payload = json.dumps(
            [1, str(owner_id), source, source_record_id, namespace],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
        return self._post(
            "hmac/identity-lookup/sha2-256",
            {"input": base64.b64encode(payload).decode("ascii"), "key_version": version},
            "hmac",
        )


class DEKCache:
    def __init__(self, capacity=1024, ttl=60, clock=time.monotonic):
        if not 1 <= capacity <= 1024 or not 0 < ttl <= 60:
            raise ValueError("Cache exceeds security bounds")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.entries = OrderedDict()
        self.lock = threading.RLock()
        self.timer = None

    def get(self, key):
        with self.lock:
            entry = self.entries.pop(key, None)
            if entry is None or self.clock() >= entry[0]:
                return None
            self.entries[key] = entry
            return entry[1]

    def put(self, identity, key):
        with self.lock:
            if self.timer is None:
                self.timer = threading.Timer(self.ttl, self.clear)
                self.timer.daemon = True
                self.timer.start()
            self.entries[identity] = (self.clock() + self.ttl, key)
            self.entries.move_to_end(identity)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)

    def clear(self):
        with self.lock:
            self.entries.clear()
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None


class EnvelopeService:
    def __init__(self, kms, cache=None):
        self.kms = kms
        self.cache = cache if cache is not None else DEKCache()
        self.incident_locked = False

    def lock(self):
        self.incident_locked = True
        self.cache.clear()

    def encrypt(self, plaintext, identity, authorize):
        if authorize(identity, "write") is not True:
            raise PermissionError("Record access denied")
        if self.incident_locked:
            raise KMSUnavailable("Key service unavailable")
        aad = identity.aad()
        if not isinstance(plaintext, bytes) or len(plaintext) > MAX_PAYLOAD:
            raise ValueError("Payload exceeds envelope bounds")
        key, nonce = os.urandom(32), os.urandom(12)
        try:
            wrapped = self.kms.wrap(key)
            match = re.fullmatch(r"vault:v([1-9][0-9]*):[A-Za-z0-9+/=]+", wrapped)
            if match is None:
                raise KMSUnavailable("Key service unavailable")
            return {
                "envelope_version": 1,
                "algorithm": "AES-256-GCM",
                "key_name": "clinical-dek",
                "key_version": int(match.group(1)),
                "wrapped_dek": wrapped,
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(AESGCM(key).encrypt(nonce, plaintext, aad)).decode(
                    "ascii"
                ),
                "payload_schema_version": identity.schema_version,
            }
        except KMSUnavailable:
            self.cache.clear()
            raise
        finally:
            del key

    def decrypt(self, envelope, identity, authorize):
        # This must happen even on cache hits and before any unwrap attempt.
        if authorize(identity, "read") is not True:
            raise PermissionError("Record access denied")
        if self.incident_locked:
            raise KMSUnavailable("Key service unavailable")
        try:
            aad = identity.aad()
            if not isinstance(envelope, dict) or set(envelope) != FIELDS:
                raise ValueError
            if (
                type(envelope["envelope_version"]) is not int
                or envelope["envelope_version"] != 1
                or envelope["algorithm"] != "AES-256-GCM"
                or envelope["key_name"] != "clinical-dek"
                or type(envelope["key_version"]) is not int
                or envelope["key_version"] < 1
                or type(envelope["payload_schema_version"]) is not int
                or envelope["payload_schema_version"] != identity.schema_version
            ):
                raise ValueError
            wrapped = envelope["wrapped_dek"]
            if not isinstance(wrapped, str) or len(wrapped) > 2048:
                raise ValueError
            match = re.fullmatch(r"vault:v([1-9][0-9]*):[A-Za-z0-9+/=]+", wrapped)
            if match is None or int(match.group(1)) != envelope["key_version"]:
                raise ValueError
            if (
                not isinstance(envelope["ciphertext"], str)
                or len(envelope["ciphertext"]) > (MAX_PAYLOAD + 16) * 4 // 3 + 4
            ):
                raise ValueError
            if not isinstance(envelope["nonce"], str) or len(envelope["nonce"]) != 16:
                raise ValueError
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
            if len(nonce) != 12 or not 16 <= len(ciphertext) <= MAX_PAYLOAD + 16:
                raise ValueError
            cache_id = hashlib.sha256(
                aad + json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
            ).digest()
            key = self.cache.get(cache_id)
            cache_miss = key is None
            if cache_miss:
                key = self.kms.unwrap(wrapped)
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
            if cache_miss:
                self.cache.put(cache_id, key)
            return plaintext
        except KMSUnavailable:
            self.cache.clear()
            raise
        except (ValueError, TypeError, KeyError, InvalidTag, IntegrityError):
            self.cache.clear()
            log.warning("envelope_integrity_failure")
            raise IntegrityError("Invalid encrypted object") from None
        finally:
            if "key" in locals():
                del key
