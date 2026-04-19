-- Local SQLite: add scene JSON column for assistant messages.
-- Idempotent: run only if column is missing (use scripts/migrate_local_db.py).

ALTER TABLE message ADD COLUMN assistant_meta TEXT;
