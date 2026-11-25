# Local backend development

The Django backend serves the journal and phone ingestion contract. Production requires explicit deployment settings and approved release evidence.

## Runtime

Python 3.12, PostgreSQL 16 and dependencies pinned by `uv.lock`:

```sh
uv sync --frozen
uv run python backend/manage.py migrate
uv run python backend/manage.py check
uv run pytest -q
uv run ruff check --config pyproject.toml backend tests/integration
python3 scripts/check_security_contracts.py
```

The development database defaults to `health03_dev`. Set `PGUSER` to your local PostgreSQL role. That database role has CREATEDB for disposable test databases; it is **not** the eventual production service role. Tests create and destroy `test_health03_dev`. No synthetic accounts are seeded into the normal database automatically. The development signing key is generated into ignored `.local/django-secret` with mode 0600.

The default hostnames are deliberately nonproduction: `https://dashboard.health03.test` and `https://api.health03.test`. Secure cookies and CSRF are enforced in integration tests using HTTPS requests. Run the development server only on loopback. A real browser walkthrough requires local TLS and name resolution, which is not yet provisioned. See ../operations/pi-production.md for production configuration.

## Implemented browser boundary

- `GET /api/v1/auth/bootstrap`: public CSRF token and login configuration, no account/health data.
- `POST /api/v1/auth/invitation`: CSRF-protected, rate-limited exchange of an invitation secret for a server-held enrollment context. Send token in JSON, never a URL.
- Maintained allauth browser login, signup, email verification, password reset, password reauthentication, password change and logout under `/_allauth/browser/v1/`.
- `GET /api/v1/session`: requires a verified, active, enrolled account **and** recorded password authentication; returns safe session metadata and currently empty health capabilities.
- `POST /api/v1/session/activity`: server-clock idle extension, capped by the absolute deadline. Polling does not extend either deadline.
- `GET /health/live`: process liveness only.

Browser sessions expire after 15 idle minutes or 12 absolute hours. Step-up expires after five minutes. Credential changes/reset invalidate session security records and change the account epoch; ordinary password login is required again. Password reset is issued only to an enrolled account's verified address and expires after one hour. Recovery mail currently goes to the in-memory test backend, never an external mailbox. Credential reset/change also revokes native token families; download tickets remain unexposed.

Allauth rate-limit state uses a shared PostgreSQL JSON cache. Atomic add and increment support its maintained locking protocol; it never unpickles database content. API responses use no-store and exact-origin credentialed CORS. Browser routes reject Authorization credentials.

## Operator enrollment

```sh
uv run python backend/manage.py bootstrap_owner
```

Prompts for an email and a new private handoff file outside the repository. Creates a 72-hour hashed-secret enrollment, refuses an existing owner or active owner invitation, and writes the raw secret only into a newly created mode-0600 file. It does not create a usable login, print the token, or send mail. Enrollment still requires a password and email verification. Do not bootstrap a real owner while the synthetic release gates remain open.

## Synthetic native authorization

Register the fixed development client with `uv run python backend/manage.py register_uploader`. It is public, uses the exact configured HTTPS callback, and requires authorization-code/S256. No application secret belongs in the phone app. Only `ingest:write` and `ingest:status` are accepted; OIDC and dynamic registration are disabled and all toolkit RFC 9700 gates are enabled.

`GET /o/authorize/` validates the request before storing it behind a short-lived, browser-bound opaque continuation. The only handoff to Pages is a fixed `/login` or `/reauthenticate` route plus that continuation ID. `/o/continue/<id>/` requires owner eligibility and fresh password verification, then renders a CSRF-protected consent form. The owner can create a labeled installation or reconnect an existing one. Code/device binding is stored on the Pi; token request body fields cannot select another device or owner.

The standard form-encoded `/o/token/` and `/o/revoke_token/` endpoints reject browser session cookies. Tokens are hash-only at rest. Access tokens last five minutes; refresh families have explicit 30-day idle and immutable 180-day absolute deadlines. Rotation uses zero grace; replay revokes the family. Reconnecting an installation replaces its prior family. A database transaction/advisory lock serializes native exchanges and revocation on this personal server, including concurrent refreshes. Throughput/load qualification remains S03 work.

`GET /api/v1/ingestion/config` authenticates only a valid device-bound bearer token and returns its ID, midnight schedule, UTC timezone, empty command/capability metadata, and `ingestion_ready:false`. It returns no health records. Ingestion itself is not implemented. Owners can list devices and revoke them through CSRF-protected browser endpoints; revocation does not require another step-up.

Run `uv run python backend/manage.py prune_native_evidence` for native cleanup. It retains refresh replay evidence until the family's absolute expiry plus seven days, even after early revocation. **Do not schedule the toolkit's generic `cleartokens` command**, which does not implement this application's retention rule. No cleanup scheduler is installed yet.

The callback uses a synthetic `.test` hostname. No production Android package/signing fingerprint or `assetlinks.json` has been claimed or published. No actual Android client or Pages login handoff has passed an end-to-end browser/device test yet.
