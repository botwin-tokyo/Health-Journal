"""Initialize only the local synthetic key service. Secrets never go to stdout.

The three share files here are a development convenience, NOT offline custody.
Do not use this procedure to admit real patient data or claim S02/S07 completion.
"""

import json
import os
import ssl
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
OPERATOR = Path.home() / ".local/share/health03/operator"
PKI = OPERATOR / "synthetic-pki"
RECOVERY = OPERATOR / "synthetic-recovery"
ADDRESS = "https://127.0.0.1:8200"


def private_file(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())


def checked(client, method, path, body=None):
    response = client.request(method, "/v1/" + path, json=body)
    if response.status_code >= 300:
        raise RuntimeError(
            f"Key-service provisioning failed: {method} {path}: HTTP {response.status_code}"
        )
    return response.json() if response.content else {}


def main():
    context = ssl.create_default_context(cafile=str(PKI / "server-ca.crt"))
    with httpx.Client(base_url=ADDRESS, verify=context, timeout=20, trust_env=False) as client:
        initialized = checked(client, "GET", "sys/init")["initialized"]
        pending = OPERATOR / "synthetic-bootstrap-root.pending"
        if not initialized:
            RECOVERY.mkdir(mode=0o700)
            result = checked(client, "PUT", "sys/init", {"secret_shares": 3, "secret_threshold": 2})
            private_file(pending, result["root_token"])
            for i, share in enumerate(result["keys_base64"], 1):
                private_file(RECOVERY / f"share-{i}", share)
            del result
        if not pending.exists():
            raise RuntimeError(
                "Already initialized without a pending bootstrap; use operator certificate maintenance"
            )
        if checked(client, "GET", "sys/seal-status")["sealed"]:
            for i in (1, 2):
                checked(client, "PUT", "sys/unseal", {"key": (RECOVERY / f"share-{i}").read_text()})
        client.headers["X-Vault-Token"] = pending.read_text()
        for _ in range(20):
            audits = checked(client, "GET", "sys/audit")["data"]
            if "health03/" in audits:
                break
            time.sleep(0.25)
        if "health03/" not in audits:
            raise RuntimeError("Declarative audit device must be enabled before provisioning")
        mounts = checked(client, "GET", "sys/mounts")["data"]
        if "transit/" not in mounts:
            checked(client, "POST", "sys/mounts/transit", {"type": "transit"})
        for name in ("clinical-dek", "auth-envelope", "identity-lookup"):
            checked(
                client,
                "POST",
                "transit/keys/" + name,
                {
                    "type": "hmac" if name == "identity-lookup" else "aes256-gcm96",
                    **({"key_size": 32} if name == "identity-lookup" else {}),
                    "exportable": False,
                    "allow_plaintext_backup": False,
                },
            )
        for role in ("app", "operator"):
            checked(
                client,
                "PUT",
                "sys/policies/acl/health03-" + role,
                {"policy": (REPO / f"infra/openbao/{role}-policy.hcl").read_text()},
            )
        methods = checked(client, "GET", "sys/auth")["data"]
        if "cert/" not in methods:
            checked(client, "POST", "sys/auth/cert", {"type": "cert"})
        for role in ("app", "operator"):
            checked(
                client,
                "POST",
                "auth/cert/certs/health03-" + role,
                {
                    "certificate": (PKI / f"health03-{role}.crt").read_text(),
                    "token_policies": ["health03-" + role],
                    "token_no_default_policy": True,
                    "token_ttl": "30m" if role == "app" else "15m",
                    "token_period": "30m" if role == "app" else 0,
                    "token_explicit_max_ttl": "24h" if role == "app" else "1h",
                },
            )
        operator_context = ssl.create_default_context(cafile=str(PKI / "server-ca.crt"))
        operator_context.load_cert_chain(
            str(PKI / "health03-operator.crt"), str(PKI / "health03-operator.key")
        )
        with httpx.Client(
            base_url=ADDRESS, verify=operator_context, timeout=20, trust_env=False
        ) as operator:
            login = checked(operator, "POST", "auth/cert/login", {"name": "health03-operator"})
            operator.headers["X-Vault-Token"] = login["auth"]["client_token"]
            del login
            info = checked(operator, "GET", "transit/keys/clinical-dek")["data"]
            assert not info["exportable"] and not info["allow_plaintext_backup"]
            checked(operator, "POST", "auth/token/revoke-self", {})
        checked(client, "POST", "auth/token/revoke-self", {})
        assert client.get("/v1/auth/token/lookup-self").status_code == 403
        pending.unlink()
    print(
        json.dumps(
            {
                "initialized": True,
                "shares": 3,
                "threshold": 2,
                "root_token_revoked": True,
                "operator_certificate_verified": True,
                "offline_recovery_custody_complete": False,
                "synthetic_only": True,
            }
        )
    )


if __name__ == "__main__":
    main()
