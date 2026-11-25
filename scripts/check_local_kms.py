"""Live synthetic checks. Never print keys, ciphertext, tokens or plaintext."""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from crypto.envelopes import EnvelopeService, Identity, IntegrityError, TransitKMS


def main():
    kms = TransitKMS()
    service = EnvelopeService(kms)
    identity = Identity(uuid.uuid4(), "clinical_record", uuid.uuid4(), uuid.uuid4(), 1)

    def authorize_synthetic(identity, action):
        return True  # Synthetic fixture only, never app policy.

    envelope = service.encrypt(b"fictional encryption probe", identity, authorize_synthetic)
    assert service.decrypt(envelope, identity, authorize_synthetic) == b"fictional encryption probe"
    other = Identity(uuid.uuid4(), identity.kind, identity.object_id, identity.revision_id, 1)
    try:
        service.decrypt(envelope, other, authorize_synthetic)
        raise AssertionError("AAD isolation failed")
    except IntegrityError:
        pass
    forbidden = [
        "/v1/transit/keys/clinical-dek/rotate",
        "/v1/transit/keys/clinical-dek/config",
        "/v1/transit/export/encryption-key/clinical-dek",
        "/v1/transit/backup/clinical-dek",
    ]
    for route in forbidden:
        response = (
            kms.client.post(route, json={})
            if route.endswith(("/rotate", "/config"))
            else kms.client.get(route)
        )
        assert response.status_code == 403, "App key-admin policy denial failed"
    first = kms.identity_digest(identity.owner_id, "fictional-source", "fictional-id", "test", 1)
    second = kms.identity_digest(identity.owner_id, "fictional-source", "fictional-id", "test", 1)
    assert first == second and first.startswith("vault:v1:")
    assert first != kms.identity_digest(uuid.uuid4(), "fictional-source", "fictional-id", "test", 1)
    kms.close()
    print(
        json.dumps(
            {
                "real_kms_roundtrip": True,
                "aad_isolation": True,
                "application_key_admin_denied": True,
                "scoped_hmac": True,
                "synthetic_only": True,
            }
        )
    )


if __name__ == "__main__":
    main()
