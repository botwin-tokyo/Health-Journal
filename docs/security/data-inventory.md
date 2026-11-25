# Data inventory and storage classification

The machine-readable [column inventory](../../contracts/security/data-inventory.json) is the review allowlist for future migrations. It describes planned entities, not existing tables. New columns require a classification before migration.

| Entity | Access owner | Envelope-encrypted fields |
| --- | --- | --- |
| Account | patient/account scoped | No clinical payload; restricted metadata only |
| SessionSecurity | patient/account scoped | No clinical payload; restricted metadata only |
| Patient | patient/account scoped | No clinical payload; restricted metadata only |
| PreferenceRevision | patient/account scoped | preferences_payload |
| ProfileRevision | patient/account scoped | profile_payload |
| SourceConnection | patient/account scoped | external_identity, labels, firmware_metadata |
| DeviceRegistration | patient/account scoped | label |
| CapabilityReceipt | patient/account scoped | evidence |
| Record | patient/account scoped | source_identity |
| RecordRevision | patient/account scoped | payload, provenance, original_units, client_digest |
| RecordLink | patient/account scoped | No clinical payload; restricted metadata only |
| MetricDefinition | operator | No clinical payload; restricted metadata only |
| ObservationIndex | patient/account scoped | No clinical payload; restricted metadata only |
| BlobObject | patient/account scoped | content, original_filename |
| IngestBatch | patient/account scoped | original_envelope |
| IngestItemReceipt | patient/account scoped | source_identity, client_digest, rejection_evidence |
| SourceTombstone | patient/account scoped | source_identity |
| Job | patient/account scoped | No clinical payload; restricted metadata only |
| OutboxEvent | patient/account scoped | No clinical payload; restricted metadata only |
| DailyDesignation | patient/account scoped | reason |
| AggregateSnapshot | patient/account scoped | result, series_definition, exclusions |
| BaselineSnapshot | patient/account scoped | result, series_definition, exclusions |
| Dependency | patient/account scoped | No clinical payload; restricted metadata only |
| JournalRevision | patient/account scoped | title, text, feeling, symptoms, energy, tags |
| MedicationEventRevision | patient/account scoped | name, dose, unit, note |
| QuestionRevision | patient/account scoped | text |
| LabReport | patient/account scoped | No clinical payload; restricted metadata only |
| LabReportRevision | patient/account scoped | patient_identifiers, accession, report_metadata, original_text |
| LabResult | patient/account scoped | test_label, test_code, specimen, method, result, operator, unit, reference_interval, flags, comments |
| ExtractionField | patient/account scoped | raw_text, proposed_value, reviewer_correction, match_evidence |
| DoctorGrant | patient/account scoped | No clinical payload; restricted metadata only |
| GrantRevision | patient/account scoped | No clinical payload; restricted metadata only |
| GrantDocument | patient/account scoped | No clinical payload; restricted metadata only |
| Invitation | patient/account scoped | No clinical payload; restricted metadata only |
| ReviewDraft | patient/account scoped | title, selection |
| ReportSnapshot | patient/account scoped | canonical_content |
| ExportArtifact | patient/account scoped | No clinical payload; restricted metadata only |
| DownloadTicket | patient/account scoped | No clinical payload; restricted metadata only |
| AuditEvent | patient/account scoped | optional_ip_user_agent |
| DeletionRequest | patient/account scoped | No clinical payload; restricted metadata only |
| RetentionRun | operator | No clinical payload; restricted metadata only |
| OAuthApplication | operator | No clinical payload; restricted metadata only |
| OAuthGrant | patient/account scoped | No clinical payload; restricted metadata only |
| OAuthTokenFamily | patient/account scoped | No clinical payload; restricted metadata only |
| OAuthAccessToken | patient/account scoped | No clinical payload; restricted metadata only |
| OAuthRefreshToken | patient/account scoped | No clinical payload; restricted metadata only |
| RateLimitEntry | operator | No clinical payload; restricted metadata only |
| BackupManifest | operator | No clinical payload; restricted metadata only |

## Class meanings

- `envelope_encrypted`: fresh AES-256-GCM envelope per immutable revision/blob; values, text, originals, units, profile and source identifiers are encrypted. Invalid/experimental records remain sensitive.
- `routing_metadata`: minimum IDs, dates, revision counters and policy metadata for bounded selection. These reveal activity and must be protected by host/database access controls and encrypted backups. Not anonymous data.
- `authentication_restricted`: email, Django password hashes, reset/verification state and session data. Raw reusable tokens are prohibited; hashed tokens are compared through maintained libraries. Do not claim application envelopes hide every authentication column.
- `envelope_metadata`/`ciphertext`: wrapped key, nonce, schema and ciphertext. Never plaintext DEKs.
- Parser plaintext exists only in bounded memory/tmpfs for one authorized job; no network, application credentials or normal-disk scratch.

Patient/record relationships must match at both ends. Shared questions omit their owner-only parent relation. Audit events contain action metadata only; query text, notes, filenames, health values and secrets are forbidden. Source HMACs are keyed and versioned. Tombstones retain minimal encrypted identity only to prevent resurrection.

Health records remain until owner deletion; deny immediately and purge live ciphertext/dependent artifacts within 24 hours. Backups age out in 35 days. Audit 365 days; operational logs 14 days; export files 24 hours; raw batches 30 days after durable evidence promotion; verbose receipts 90 days. Preserve minimal replay evidence as specified in S05.

Original PDFs, curves, reviewed OCR, reports and archive parts are encrypted blobs. Database and object backups use encrypted restic sets. Local OpenBao sealed state and recovery shares remain outside Git; shares are operator secrets, not application configuration.

Use fictional inputs for tests and documentation.
