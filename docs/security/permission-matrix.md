# Permission matrix

Generated from [operations.json](../../contracts/security/operations.json). Each planned domain operation appears in the [OpenAPI security surface](../../contracts/openapi.yaml); DTO completion and library-auth schemas belong to B00. Default is deny, including unknown routes and role combinations.

| Operation | Allowed principals | Required policy | CSRF | Fresh password |
| --- | --- | --- | --- | --- |
| `GET /api/v1/auth/bootstrap` | anonymous, owner, doctor | public_auth_configuration | False | False |
| `GET /api/v1/session` | owner, doctor | eligible_account_and_owned_context | False | False |
| `POST /api/v1/session/context` | owner, doctor | eligible_account_and_owned_context | True | False |
| `POST /api/v1/session/activity` | owner, doctor | eligible_account_and_owned_context | True | False |
| `GET /api/v1/catalog/metrics` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/blood-pressure` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/overview` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/breathing` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/breathing/sessions/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/breathing/manual-sessions` | owner | owner_only | True | False |
| `PATCH /api/v1/breathing/sessions/{id}/designation` | owner | owner_only | True | False |
| `POST /api/v1/breathing/imports` | owner | owner_only | True | False |
| `GET /api/v1/breathing/imports/{id}` | owner | owner_only | False | False |
| `PATCH /api/v1/breathing/imports/{id}/review` | owner | owner_only | True | False |
| `POST /api/v1/breathing/imports/{id}/commit` | owner | owner_only | True | False |
| `GET /api/v1/body` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/body/weights` | owner | owner_only | True | False |
| `PATCH /api/v1/body/weights/{id}` | owner | owner_only | True | False |
| `DELETE /api/v1/body/weights/{id}` | owner | owner_only | True | False |
| `PUT /api/v1/body/days/{date}/representative` | owner | owner_only | True | False |
| `GET /api/v1/sleep-activity` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/activity/workouts/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/baselines` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/baselines/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/baselines/preview` | owner | owner_only | True | False |
| `POST /api/v1/baselines` | owner | owner_only | True | False |
| `POST /api/v1/baselines/{id}/retire` | owner | owner_only | True | False |
| `GET /api/v1/journal/entries` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/journal/entries` | owner | owner_only | True | False |
| `GET /api/v1/journal/entries/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `PATCH /api/v1/journal/entries/{id}` | owner | owner_only | True | False |
| `DELETE /api/v1/journal/entries/{id}` | owner | owner_only | True | False |
| `POST /api/v1/journal/search` | owner, doctor | current_patient_grant_and_dependencies | True | False |
| `GET /api/v1/journal/questions` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/journal/questions` | owner | owner_only | True | False |
| `GET /api/v1/journal/questions/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `PATCH /api/v1/journal/questions/{id}` | owner | owner_only | True | False |
| `DELETE /api/v1/journal/questions/{id}` | owner | owner_only | True | False |
| `GET /api/v1/journal/medication-events` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/journal/medication-events` | owner | owner_only | True | False |
| `GET /api/v1/journal/medication-events/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `PATCH /api/v1/journal/medication-events/{id}` | owner | owner_only | True | False |
| `DELETE /api/v1/journal/medication-events/{id}` | owner | owner_only | True | False |
| `GET /api/v1/labs/reports` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/labs/reports/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/labs/uploads` | owner | owner_only | True | False |
| `GET /api/v1/labs/imports/{id}` | owner | owner_only | False | False |
| `PATCH /api/v1/labs/reports/{id}/review` | owner | owner_only | True | False |
| `POST /api/v1/labs/reports/{id}/publish` | owner | owner_only | True | False |
| `GET /api/v1/labs/trends` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `GET /api/v1/documents/{id}/content` | owner, doctor | exact_document_consent_and_current_grant | False | False |
| `GET /api/v1/settings` | owner | owner_only | False | False |
| `PATCH /api/v1/settings` | owner | owner_only | True | False |
| `GET /api/v1/devices` | owner | owner_only | False | False |
| `POST /api/v1/devices/{id}/revoke` | owner | owner_only | True | False |
| `POST /api/v1/sync/requests` | owner | owner_only | True | False |
| `GET /api/v1/sync/status` | owner | owner_only | False | False |
| `GET /api/v1/sharing/grants` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `POST /api/v1/sharing/grants` | owner | owner_only | True | False |
| `GET /api/v1/sharing/grants/{id}` | owner, doctor | current_patient_grant_and_dependencies | False | False |
| `PATCH /api/v1/sharing/grants/{id}` | owner | owner_only | True | False |
| `POST /api/v1/sharing/grants/{id}/invite` | owner | owner_only | True | True |
| `POST /api/v1/sharing/grants/{id}/revoke` | owner | owner_only | True | False |
| `GET /api/v1/review/drafts` | owner | owner_only | False | False |
| `POST /api/v1/review/drafts` | owner | owner_only | True | False |
| `GET /api/v1/review/drafts/{id}` | owner | owner_only | False | False |
| `PATCH /api/v1/review/drafts/{id}` | owner | owner_only | True | False |
| `POST /api/v1/review/drafts/{id}/snapshots` | owner | owner_only | True | False |
| `GET /api/v1/review/snapshots/{id}` | owner, doctor | artifact_audience_and_every_dependency | False | False |
| `POST /api/v1/review/snapshots/{id}/exports` | owner | owner_only | True | True |
| `POST /api/v1/exports` | owner | owner_only | True | True |
| `GET /api/v1/exports/{id}` | owner, doctor | artifact_audience_and_every_dependency | False | False |
| `POST /api/v1/exports/{id}/download-tickets` | owner, doctor | current_patient_grant_and_dependencies | True | True |
| `GET /api/v1/exports/{id}/content` | owner, doctor | artifact_audience_and_every_dependency | False | False |
| `GET /api/v1/security/status` | owner | owner_only | False | False |
| `GET /api/v1/security/sessions` | owner | owner_only | False | False |
| `POST /api/v1/security/sessions/{id}/revoke` | owner | owner_only | True | False |
| `GET /api/v1/security/access-events` | owner | owner_only | False | False |
| `POST /api/v1/account/deletion-requests` | owner | owner_only | True | True |
| `GET /api/v1/account/deletion-requests/{id}` | owner | owner_only | False | False |
| `POST /api/v1/ingestion/batches` | uploader | device_namespace_and_scope | False | False |
| `GET /api/v1/ingestion/batches/{batch_id}` | uploader | device_namespace_and_scope | False | False |
| `POST /api/v1/ingestion/assets` | uploader | device_namespace_and_scope | False | False |
| `GET /api/v1/ingestion/config` | uploader | device_namespace_and_scope | False | False |
| `POST /api/v1/ingestion/commands/{id}/ack` | uploader | device_namespace_and_scope | False | False |

## Shared enforcement rules

Authorization precedes decryption, cache access and serialization. Owner context comes from the session; never trust a body owner/role. Doctors require recipient binding, active state, unexpired fixed dates, category/action and explicit journal/question allowlists. Source PDFs require separate whole-document consent. Medication events require their own date and explicit inclusion through a shared entry. All derived dependencies must be authorized; otherwise omit the value, hidden dates/counts and delta. Owner preview uses the same selector. Out-of-scope IDs return 404.

Jobs reauthorize at enqueue, execution, readiness and download. Permission changes increment epochs transactionally. Expired artifacts, replayed tickets and cached mutation successes cannot bypass current policy. Prompt revocation has no stale ETag/step-up barrier. Uploader grants permit only their namespace, receipts and bounded config; reject mixed browser/bearer credentials.

Public auth bootstrap contains CSRF/public configuration only. Allauth login/reset/enrollment cannot grant health access before active, verified, invited password-authenticated eligibility. OAuth protocol endpoints require exact callbacks/S256 and bound device families. These library operations are tested against their pinned installed schemas in S01.

The matrix marks potential readers, not unconditional access. Session/context/grant-list operations expose only the acting account. Doctor exports require explicit download_report permission and artifact audience. Owner-only exports never become discoverable through overlapping record scope.
