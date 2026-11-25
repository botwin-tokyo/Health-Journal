# Release and pilot operation

Release evidence is pinned to a commit and dependency-lock hash. Generate it with
`scripts/build_release_evidence.py`; omitted or failed acceptance gates keep the release closed.
An operator records explicit approval and outcomes in private files, then uses
`scripts/advance_release.py --gate <private-json> --evidence <private-record>`
with `start-owner`, `record-doctor`, and finally `release`. Starting the pilot does
not authorize general production. Seven elapsed days and recorded doctor approval
are required before release. No command sends invitations. Changed candidate code
requires refreshed evidence and affected acceptance checks.

Production startup remains disabled until the full gate is authorized. A dedicated
owner pilot deployment needs the same verified deployment inputs plus an owner-only
access restriction; the general production configuration must not be bypassed for it.

Keep the previous application directory and its exact dependency environment.
Retain the migration compatibility record. When backups are enabled, take a complete backup before migration. For a deployment with backups disabled, assess irreversible migrations before cutover. Switch the current symlink only after checking schema compatibility.
On an incompatible schema, keep ingress closed and use the verified recovery
procedure. Never roll back database authorization state, the reduction ledger,
or deletion tombstones to undo a code release.

Daily: inspect service, ledger and backup monitoring. Weekly: review active devices
and grants. Monthly: review dependencies and OS patches. Quarterly and after backup
or key-format changes: perform a decrypting restore. Renew client certificates before
expiry. Annually: rotate the clinical KEK, rewrap and verify retained backup dependencies.
