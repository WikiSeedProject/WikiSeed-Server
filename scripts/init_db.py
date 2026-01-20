#!/usr/bin/env python3
"""Initialize WikiSeed database with latest schema."""

import os
import sqlite3
from pathlib import Path

# Use DATABASE_PATH env var if set (for Docker), otherwise use relative path
DB_PATH = Path(os.getenv("DATABASE_PATH", "data/db/jobs.db"))
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

    # Ensure database is written to disk
    conn.execute("PRAGMA wal_checkpoint(FULL)")
    conn.commit()
    conn.close()

    # Verify database exists
    if DB_PATH.exists():
        size = DB_PATH.stat().st_size
        print(f"✓ Database initialized at {DB_PATH} ({size} bytes)")
    else:
        print(f"✗ ERROR: Database file not found at {DB_PATH}")
        raise FileNotFoundError(f"Database not created at {DB_PATH}")


if __name__ == "__main__":
    init_database()
