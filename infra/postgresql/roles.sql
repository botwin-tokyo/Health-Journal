-- Run as the database administrator for the intended health03 database.
-- Runtime roles use Unix-socket peer auth; migrations are operator-only.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='health03-migrate') THEN CREATE ROLE "health03-migrate" LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='health03-app') THEN CREATE ROLE "health03-app" LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='health03-worker') THEN CREATE ROLE "health03-worker" LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='health03-backup') THEN CREATE ROLE "health03-backup" LOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='health03-retention') THEN CREATE ROLE "health03-retention" LOGIN; END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO "health03-app", "health03-worker", "health03-backup", "health03-retention";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "health03-app", "health03-worker";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "health03-app", "health03-worker";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "health03-backup";
ALTER DEFAULT PRIVILEGES FOR ROLE "health03-migrate" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "health03-app", "health03-worker";
ALTER DEFAULT PRIVILEGES FOR ROLE "health03-migrate" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "health03-app", "health03-worker";
ALTER DEFAULT PRIVILEGES FOR ROLE "health03-migrate" IN SCHEMA public GRANT SELECT ON TABLES TO "health03-backup";
-- Apply audit-specific revocations after migrations using audit-privileges.sql.
