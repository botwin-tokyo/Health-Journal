# Shared authorization foundation

`backend/access/policy.py` supplies the server-derived `AuthorizationContext`. It reloads account state, validates the current password-established session, and resolves only a server-session-selected grant. An owner may select an owned grant for preview; a doctor may select only a grant addressed to that account. Invalid, inactive, revoked, expired, future, overlong or recipient-ineligible grants fail closed with no record details.

`RecordRef` is a typed routing/scope description, **not a request DTO**. Domain selectors must construct it from current persisted metadata, inside a bounded selection. Never accept its owner, kind, clinical date, visibility, selections or dependencies from a client request. Domain selectors and clinical-record endpoints remain unimplemented, so this foundation does not yet claim end-to-end clinical authorization.

The policy enforces:

- Owner isolation; owner preview obeys the selected doctor's scope and cannot write records.
- Inclusive persisted clinical dates, categories and permitted actions.
- Private journal exclusion and explicit journal/question selection; empty selections mean none.
- Medication event's own date and explicit selection plus an authorized shared parent.
- Optional structured-result selection, distinguishing unrestricted-within-category (`null`) from no results (`[]`).
- Explicit whole-original-document consent, separate from structured lab scope. This may intentionally allow the entire selected original outside structured date/category bounds. Generic read permission does not deliver original bytes.
- Every contributor to a derived snapshot must be authorized. A denied contributor produces only generic unavailability, with no hidden dependency count or partial fallback calculation.
- Bounded selections and dependency traversal, current grant/account checks before each envelope operation, and rejection when the selection's permission epoch changes before cached decryption.

The envelope authorizer binds the selected immutable identity, requested action and captured permission epoch. Upcoming domain selectors must load fresh metadata and compare the permission epoch around selection; they cannot reuse an old `RecordRef` as permanent authorization. Upcoming views must use the shared selector and the existing response epoch guard rather than calling the envelope service with an unconditional callback. Test-only unconditional callbacks are confined to synthetic checks/tests.

`SharingGrant` stores routing scope and account references, not health text. The internal approval service requires the owner, fresh password verification, an enrolled verified doctor, a finite valid range and expiry no later than 180 days. Drafts default to 30-day expiry. Revocation requires an eligible owner session, without another step-up. Approval/revocation increment the owner's sharing epoch transactionally. Public grant drafting/inviting/acceptance/edit endpoints are not yet exposed; tests exercise the service directly with fictional accounts. Artifact/ticket invalidation must be integrated before those features are exposed.

`POST /api/v1/session/context` accepts only `grant_id`, validates its relationship and current scope, and returns the minimal context-reset acknowledgement. `GET /api/v1/session` reports owner/doctor/owner-preview/no-grant context and an opaque permission epoch. Current clinical capabilities remain empty because clinical endpoints are not implemented. Protected responses discard their body if the permission epoch changes during the request. Invalid contexts can be cleared through the context endpoint.

Frontend abort/clear behavior, grants invitation UX, domain/query selectors, report jobs and downloads must still be integrated and tested before the S01/S02 exit gates can pass.
