# ADR 0003 — Security contracts and domain invariants

## Browser and native identities

Pages renders the login form; Django/allauth verifies email/password and issues an API-host Secure/HttpOnly cookie. Use explicit frontend/API origins, CSRF bootstrap, exact CORS, 15-minute idle and 12-hour absolute session expiry. Polling does not extend idle time. Five-minute fresh-password verification protects scope expansion, exports and credential changes; prompt revocation remains available. Invite-only verified enrollment is required. Browser bearer tokens and persistent health caches are prohibited.

The Android public client uses AppAuth/system browser, authorization code and S256 PKCE against Django OAuth Toolkit. Use exact HTTPS App Links, 300-second access tokens, rotating refresh families with 30-day idle/180-day absolute lifetime and zero replay grace. Persist hashed tokens only. Device/namespace binding comes from approved authorization, not a token request body. A lost refresh response may require reconnecting without discarding the queue. No browser session can upload and no uploader credential can read health records.

## Encryption and policy

Use maintained AES-256-GCM envelopes, a fresh 32-byte DEK/12-byte nonce per immutable revision/blob and local OpenBao Transit wrapping. AAD is the exact canonical array in S02: version, patient UUID, kind, object UUID, revision UUID, schema version. Authenticate completely before returning plaintext. Authorization precedes unwrap/cache lookup. Keys are cached only in memory within the stated 60-second/1024-entry bound. HMAC identity lookup has separate versioned keys and dual-read/reindex rotation. No local plaintext fallback when OpenBao is unavailable.

Apply one patient/grant selector everywhere, including search, counts, derived contributors, preview, exports and cached idempotency replay. Preserve all original contributors; withhold a derived value if any dependency is unauthorized. Never silently recalculate a different doctor baseline. Journal/questions require explicit allowlists and shared visibility. Whole original PDFs have separate consent. Jobs do not retain permanent authorization.

## Parsing

Use an unprivileged preprovisioned systemd helper with no IP networking, no DB/KMS credentials, bounded tmpfs and a private Unix socket checking the worker UID. Only fixed operation/template IDs and bounded file descriptors cross IPC. No arbitrary shell/path/URL/template input, sudo, remote OCR or cloud AI. Local pypdf/OCR and trusted-template WeasyPrint render under quotas. The worker authorizes/decrypts and validates/encrypts returned data.

## Chronology, revisions and source qualification

Persist clinical_date and original timezone/offset. Sleep uses wake date; labs specimen date; date-only inputs have no invented time. Display timezone changes never regroup historical dates. One explicit morning-weight designation and one real pulmonary trial representative prevent duplicate weighting. Revision IDs are immutable, source identity is stable, and stale queues cannot resurrect tombstoned data. Native adapter receipts, units, statistics and method/profile versions establish comparability; transport success is not clinical validity.

## Consequences and migration

These contracts are enforced by S01–S06, not merely by an ADR. The S00 OpenAPI file is a security surface inventory and explicitly marks operations unimplemented. B00 must complete schemas, deterministic fixtures and generated client types before frontend integration. There is no existing application database to migrate. Future columns/operations must update the inventory, permission matrix and tests in the same change.
