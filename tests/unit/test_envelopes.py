import base64
import os
import uuid
from dataclasses import replace

import pytest
from crypto.envelopes import DEKCache, EnvelopeService, Identity, IntegrityError, KMSUnavailable
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class FictionalKMS:
    """Test-only ephemeral KEK. The application has no fallback implementation."""

    def __init__(self):
        self.key = os.urandom(32)
        self.calls = 0
        self.unavailable = False

    def wrap(self, key):
        nonce = os.urandom(12)
        return (
            "vault:v1:"
            + base64.b64encode(nonce + AESGCM(self.key).encrypt(nonce, key, b"test")).decode()
        )

    def unwrap(self, value):
        self.calls += 1
        if self.unavailable:
            raise KMSUnavailable("Key service unavailable")
        raw = base64.b64decode(value.split(":", 2)[2])
        return AESGCM(self.key).decrypt(raw[:12], raw[12:], b"test")


def allowed(identity, action):
    return True


@pytest.fixture
def identity():
    return Identity(
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "clinical_record",
        uuid.UUID("00000000-0000-0000-0000-000000000002"),
        uuid.UUID("00000000-0000-0000-0000-000000000003"),
        1,
    )


def test_aad_golden_bytes(identity):
    assert (
        identity.aad()
        == b'[1,"00000000-0000-0000-0000-000000000001","clinical_record","00000000-0000-0000-0000-000000000002","00000000-0000-0000-0000-000000000003",1]'
    )


def test_fresh_keys_and_nonces(identity):
    service = EnvelopeService(FictionalKMS())
    first = service.encrypt(b"fictional data", identity, allowed)
    second = service.encrypt(b"fictional data", identity, allowed)
    assert first["nonce"] != second["nonce"]
    assert first["wrapped_dek"] != second["wrapped_dek"]
    assert first["ciphertext"] != second["ciphertext"]
    assert service.decrypt(first, identity, allowed) == b"fictional data"


@pytest.mark.parametrize(
    "field", ["owner_id", "object_id", "revision_id", "kind", "schema_version"]
)
def test_wrong_identity_fails_closed(identity, field):
    service = EnvelopeService(FictionalKMS())
    envelope = service.encrypt(b"fictional data", identity, allowed)
    value = "journal_entry" if field == "kind" else 2 if field == "schema_version" else uuid.uuid4()
    with pytest.raises(IntegrityError):
        service.decrypt(envelope, replace(identity, **{field: value}), allowed)
    assert not service.cache.entries


@pytest.mark.parametrize(
    "field,value",
    [
        ("envelope_version", True),
        ("envelope_version", 2),
        ("algorithm", "AES-CBC"),
        ("key_name", "unapproved-key"),
        ("key_version", 2),
        ("nonce", "malformed"),
        ("ciphertext", "not base64!"),
        ("wrapped_dek", "unknown:v1:AA=="),
        ("payload_schema_version", True),
    ],
)
def test_malformed_envelope_rejected_before_unwrap(identity, field, value):
    kms = FictionalKMS()
    service = EnvelopeService(kms)
    envelope = service.encrypt(b"fictional data", identity, allowed)
    envelope[field] = value
    with pytest.raises(IntegrityError):
        service.decrypt(envelope, identity, allowed)
    assert kms.calls == 0


@pytest.mark.parametrize("field", ["nonce", "ciphertext"])
def test_tampering_releases_no_plaintext(identity, field):
    service = EnvelopeService(FictionalKMS())
    envelope = service.encrypt(b"fictional data", identity, allowed)
    raw = bytearray(base64.b64decode(envelope[field]))
    raw[-1] ^= 1
    envelope[field] = base64.b64encode(raw).decode()
    with pytest.raises(IntegrityError):
        service.decrypt(envelope, identity, allowed)
    assert not service.cache.entries


def test_authorization_precedes_cached_key_access(identity):
    kms = FictionalKMS()
    service = EnvelopeService(kms)
    envelope = service.encrypt(b"fictional data", identity, allowed)
    service.decrypt(envelope, identity, allowed)
    with pytest.raises(PermissionError):
        service.decrypt(envelope, identity, lambda identity, action: False)
    assert kms.calls == 1


def test_cache_hits_do_not_extend_sixty_second_deadline(identity):
    now = [0]
    kms = FictionalKMS()
    service = EnvelopeService(kms, DEKCache(clock=lambda: now[0]))
    envelope = service.encrypt(b"fictional data", identity, allowed)
    service.decrypt(envelope, identity, allowed)
    now[0] = 30
    service.decrypt(envelope, identity, allowed)
    assert kms.calls == 1
    now[0] = 60
    service.decrypt(envelope, identity, allowed)
    assert kms.calls == 2
    service.cache.clear()


def test_known_kms_failure_and_incident_lock_clear_cache(identity):
    kms = FictionalKMS()
    service = EnvelopeService(kms)
    first = service.encrypt(b"fictional data", identity, allowed)
    second = service.encrypt(b"fictional data", identity, allowed)
    service.decrypt(first, identity, allowed)
    kms.unavailable = True
    with pytest.raises(KMSUnavailable):
        service.decrypt(second, identity, allowed)
    assert not service.cache.entries
    service.lock()
    with pytest.raises(KMSUnavailable):
        service.decrypt(first, identity, allowed)


def test_cache_bounds():
    with pytest.raises(ValueError):
        DEKCache(capacity=1025)
    with pytest.raises(ValueError):
        DEKCache(ttl=61)
    cache = DEKCache(capacity=2)
    for value in range(3):
        cache.put(value, b"fictional key")
    assert len(cache.entries) == 2
    assert cache.get(0) is None
    cache.clear()


@pytest.mark.parametrize(
    "status,body",
    [
        (503, {}),
        (403, {}),
        (200, {}),
        (200, {"data": {"plaintext": []}}),
        (200, {"data": {"plaintext": "AAAA"}}),
    ],
)
def test_untrusted_or_unavailable_kms_response_is_generic(status, body):
    import httpx
    from crypto.envelopes import TransitKMS

    kms = TransitKMS()
    kms.close()
    kms.client = httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)),
    )
    with pytest.raises(KMSUnavailable, match="^Key service unavailable$"):
        kms.unwrap("vault:v1:fictional")
    kms.close()
