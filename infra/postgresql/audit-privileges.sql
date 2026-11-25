REVOKE UPDATE, DELETE, TRUNCATE ON operations_auditevent FROM "health03-app", "health03-worker", "health03-backup";
GRANT SELECT, INSERT ON operations_auditevent TO "health03-app", "health03-worker";
GRANT SELECT, DELETE ON operations_auditevent TO "health03-retention";
GRANT SELECT, INSERT, UPDATE ON operations_backupset TO "health03-backup";
GRANT SELECT, INSERT ON operations_auditevent TO "health03-backup";
GRANT SELECT, UPDATE, DELETE ON artifacts_securerecord, artifacts_downloadticket, artifacts_securityjob, operations_cacheentry TO "health03-retention";
-- The retention command expires exports, idempotency receipts and transport evidence.
GRANT SELECT ON reports_exportpart, ingest_ingestbatch TO "health03-retention";
GRANT SELECT, UPDATE ON reports_exportbundle, operations_deletionrequest TO "health03-retention";
GRANT SELECT, DELETE ON records_actionreceipt, records_mutation, ingest_itemreceipt TO "health03-retention";
