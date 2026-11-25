"""Synthetic ciphertext probe for an explicit operator restart/unseal drill."""

import json
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from crypto.envelopes import EnvelopeService, Identity, KMSUnavailable, TransitKMS  # noqa: E402


def allowed(identity, action):
    return True  # Only the fictional record created below is in this drill.


def main():
    phase = sys.argv[1]
    path = root / ".local/synthetic-restart-envelope.json"
    kms = TransitKMS()
    service = EnvelopeService(kms)
    if phase == "prepare":
        identity = Identity(uuid.uuid4(), "clinical_record", uuid.uuid4(), uuid.uuid4(), 1)
        envelope = service.encrypt(b"fictional restart recovery probe", identity, allowed)
        path.write_text(
            json.dumps(
                {
                    "owner": str(identity.owner_id),
                    "object": str(identity.object_id),
                    "revision": str(identity.revision_id),
                    "envelope": envelope,
                }
            )
        )
    else:
        saved = json.loads(path.read_text())
        identity = Identity(
            uuid.UUID(saved["owner"]),
            "clinical_record",
            uuid.UUID(saved["object"]),
            uuid.UUID(saved["revision"]),
            1,
        )
        if phase == "sealed":
            try:
                service.decrypt(saved["envelope"], identity, allowed)
                raise AssertionError("Sealed KMS did not fail closed")
            except KMSUnavailable:
                pass
        elif phase == "recover":
            assert (
                service.decrypt(saved["envelope"], identity, allowed)
                == b"fictional restart recovery probe"
            )
            path.unlink()
        else:
            raise ValueError("Unknown drill phase")
    kms.close()
    print("Synthetic KMS restart drill: " + phase + " passed")


if __name__ == "__main__":
    main()
