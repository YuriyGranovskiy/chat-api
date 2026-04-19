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
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
