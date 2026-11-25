# Local OpenBao: synthetic deployment

The example units run an ARM64 OpenBao server and a scoped certificate-auth agent. See `infra/openbao/` and `infra/systemd/`.

The server uses persistent Raft storage, TLS on `127.0.0.1:8200`, disabled UI, a separate non-login identity, no capabilities, no core dumps and `MemorySwapMax=0`. Its cluster listener also binds loopback. OpenBao 2.7 removed the older mlock setting; this configuration uses the documented service-level swap restriction. Audit logging is declarative in this release, with raw logging disabled. Audit files live in the service-private log directory.

The app agent authenticates with a 90-day client certificate, receives a renewable 30-minute token with a 24-hour explicit maximum, verifies the server CA and loads its private key through systemd credentials. Its only application listener is `/run/health03-bao-agent/api.sock`, restricted to `health03-kms`. Grant membership only to the service users and test operator who need it. The agent forces its scoped identity; callers cannot replace it by supplying another token. No token file is exposed to the application.

The app policy permits clinical/auth-envelope wrap/unwrap and the separate identity HMAC only, plus its own token renewal lifecycle. It cannot rotate/configure/delete/export/back up Transit keys. A separate operator certificate permits maintenance. Clinical and authentication keys are nonexportable `aes256-gcm96` Transit keys; identity lookup uses a distinct 32-byte HMAC key. Application payload encryption uses independent AES-256-GCM DEKs/nonces.

## Reproduce the synthetic setup

Run only on an intended clean local installation; installer scripts refuse replacing existing services. Never point these scripts at a real-data instance.

1. Run `scripts/download_openbao.sh`: pinned upstream release, GPG fingerprint and signed SHA-256 checks, then extraction of only the binary.
2. Run `uv run python scripts/create_synthetic_bao_certificates.py` once. It refuses an existing PKI directory and never prints private keys.
3. Run the root server installer with its verified artifact directory, synthetic PKI directory, and repository directory as positional arguments. Only filesystem paths are command arguments.
4. Run `uv run python scripts/provision_synthetic_openbao.py`. It initializes three Shamir shares with a two-share threshold, verifies declarative audit, creates Transit keys/scoped certificate roles, tests operator login, and revokes/removes the temporary initialization root token. A failed provisioning attempt retains an operator-private pending token for explicit retry; successful provisioning does not.
5. Run the root agent installer with the synthetic PKI directory, repository directory and local developer username.

Operator development material is under `~/.local/share/health03/operator/`, outside this repository. The synthetic setup stores shares and test CA material locally. This intentionally does **not** satisfy offline/separated recovery custody. These files and initial TLS identities are for fictional development only. Never include them in the application/database backup or Git. No real-data release is authorized by this setup.

## Synthetic checks

```sh
sg health03-kms -c '.venv/bin/python scripts/check_local_kms.py'
sg health03-kms -c '.venv/bin/python scripts/check_kms_restart.py prepare'
sudo systemctl restart health03-openbao.service
sg health03-kms -c '.venv/bin/python scripts/check_kms_restart.py sealed'
uv run python scripts/unseal_synthetic_openbao.py
sg health03-kms -c '.venv/bin/python scripts/check_kms_restart.py recover'
```

The explicit unseal helper is **not** installed as a startup job. A restart leaves the service sealed until an operator acts. The restart drill writes only synthetic ciphertext under ignored `.local/`, then removes it after recovery. It is not a backup/restore test.

`sg health03-kms -c '.venv/bin/python scripts/check_kms_rotation.py'` is a deliberate one-off rotation/rewrap drill. It rotates the clinical KEK, confirms both old/new wraps decrypt, and confirms unchanged payload ciphertext/nonce. Do not run it as a routine health poll. Old key versions are retained. HMAC rotation/reindexing is not implemented.

The local smoke check verifies application policy denials for key rotation, configuration, export and backup, as well as owner-bound AAD and distinct-purpose HMAC. It logs only result booleans. Unit tests use ephemeral **test-only** KMS doubles; application code has no built-in or fallback encryption key.

References: [installation and signature verification](https://openbao.org/docs/install/), [declarative audit](https://openbao.org/docs/configuration/audit/), [certificate auto-auth](https://openbao.org/docs/agent-and-proxy/autoauth/methods/cert/), [agent API proxy](https://openbao.org/docs/agent-and-proxy/agent/apiproxy/). Agent proxy behavior is pinned to 2.7.2; upstream signals a future migration to its dedicated proxy command.
