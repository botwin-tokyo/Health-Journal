"""One-off synthetic operator rotation/rewrap drill; never logs secret material."""

import json
import ssl
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from crypto.envelopes import EnvelopeService, Identity, TransitKMS


def allowed(identity, action):
    return True  # This drill creates and accesses only a fictional object.


def main():
    kms = TransitKMS()
    service = EnvelopeService(kms)
    identity = Identity(uuid.uuid4(), "clinical_record", uuid.uuid4(), uuid.uuid4(), 1)
    envelope = service.encrypt(b"fictional rotation probe", identity, allowed)
    pki = Path.home() / ".local/share/health03/operator/synthetic-pki"
    context = ssl.create_default_context(cafile=str(pki / "server-ca.crt"))
    context.load_cert_chain(str(pki / "health03-operator.crt"), str(pki / "health03-operator.key"))
    import httpx

    with httpx.Client(
        base_url="https://127.0.0.1:8200", verify=context, trust_env=False, timeout=10
    ) as operator:
        response = operator.post("/v1/auth/cert/login", json={"name": "health03-operator"})
        response.raise_for_status()
        operator.headers["X-Vault-Token"] = response.json()["auth"]["client_token"]
        try:
            operator.post("/v1/transit/keys/clinical-dek/rotate", json={}).raise_for_status()
            response = operator.post(
                "/v1/transit/rewrap/clinical-dek", json={"ciphertext": envelope["wrapped_dek"]}
            )
            response.raise_for_status()
            replacement = response.json()["data"]["ciphertext"]
            newer = {
                **envelope,
                "wrapped_dek": replacement,
                "key_version": int(replacement.split(":")[1][1:]),
            }
            assert newer["key_version"] > envelope["key_version"]
            assert (
                newer["ciphertext"] == envelope["ciphertext"]
                and newer["nonce"] == envelope["nonce"]
            )
            assert service.decrypt(envelope, identity, allowed) == b"fictional rotation probe"
            assert service.decrypt(newer, identity, allowed) == b"fictional rotation probe"
        finally:
            operator.post("/v1/auth/token/revoke-self", json={}).raise_for_status()
    kms.close()
    print(
        json.dumps(
            {
                "rotation_and_rewrap": True,
                "old_envelope_still_decrypts": True,
                "clinical_ciphertext_unchanged": True,
                "synthetic_only": True,
            }
        )
    )


if __name__ == "__main__":
    main()
