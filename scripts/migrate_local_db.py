#!/usr/bin/env python3
"""
Apply SQLite migrations for the local chat.db used by app.config.Config.

Default DB path follows Flask behavior for relative sqlite paths:
<project_root>/instance/chat.db. Fallback: <project_root>/chat.db.
Override with CHAT_DB_PATH.

Usage:
  python3 scripts/migrate_local_db.py
  CHAT_DB_PATH=/path/to/chat.db python3 scripts/migrate_local_db.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "instance" / "chat.db"
FALLBACK_DB = ROOT / "chat.db"


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def migrate_entity_images(conn: sqlite3.Connection) -> bool:
    """Add image_path and image_access_token to world, persona, location."""
    changed = False
    for table in ("world", "persona", "location"):
        columns = _table_columns(conn, table)
        if not columns:
            print(f"Table `{table}` not found; skip image columns.", file=sys.stderr)
            continue
        if "image_path" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN image_path TEXT")
            changed = True
            print(f"Migration applied: {table}.image_path (TEXT, nullable).")
        if "image_access_token" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN image_access_token TEXT")
            changed = True
            print(f"Migration applied: {table}.image_access_token (TEXT, nullable).")
    if changed:
        for table in ("world", "persona", "location"):
            idx = f"ix_{table}_image_access_token"
            try:
                conn.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {table}(image_access_token) "
                    "WHERE image_access_token IS NOT NULL"
                )
            except sqlite3.OperationalError as e:
                print(f"Note: could not create index {idx}: {e}", file=sys.stderr)
        conn.commit()
    elif _table_columns(conn, "world") and "image_path" in _table_columns(conn, "world"):
        print("Entity image columns already present; nothing to do for images.")
    return True


def migrate_assistant_meta(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("PRAGMA table_info(message)")
    columns = [row[1] for row in cur.fetchall()]
    if not columns:
        print("Table `message` not found; create the schema first (run the app once).", file=sys.stderr)
        return False
    if "assistant_meta" in columns:
        print("Column message.assistant_meta already exists; nothing to do.")
        return True
    conn.execute("ALTER TABLE message ADD COLUMN assistant_meta TEXT")
    conn.commit()
    print("Migration applied: added message.assistant_meta (TEXT, nullable).")
    return True


def main() -> int:
    env_db_path = os.environ.get("CHAT_DB_PATH")
    if env_db_path:
        db_path = Path(env_db_path).resolve()
    elif DEFAULT_DB.exists():
        db_path = DEFAULT_DB.resolve()
    else:
        db_path = FALLBACK_DB.resolve()
    if not db_path.exists():
        print(
            f"No database file at {db_path}. "
            "Start the app once to create it, or set CHAT_DB_PATH.",
            file=sys.stderr,
        )
        return 1
    conn = sqlite3.connect(db_path)
    try:
        migrate_assistant_meta(conn)
        migrate_entity_images(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
