#!/usr/bin/env python3
"""Initialize WikiSeed database with latest schema."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/db/jobs.db")
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def init_database() -> None:
    """Initialize database with latest schema."""

    # Create database directory if needed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Configure SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    # Get current schema version
    try:
        cursor = conn.execute("SELECT value FROM system_state WHERE key = 'schema_version'")
        row = cursor.fetchone()
        current_version = int(row[0]) if row else 0
    except sqlite3.OperationalError:
        current_version = 0

    # Run migrations
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for migration_file in migration_files:
        # Extract version from filename (e.g., 001_initial.sql -> 1)
        version = int(migration_file.stem.split("_")[0])

        if version > current_version:
            print(f"Applying migration {migration_file.name}...")
            with open(migration_file) as f:
                conn.executescript(f.read())
            print(f"✓ Migration {version} applied")

    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_database()
