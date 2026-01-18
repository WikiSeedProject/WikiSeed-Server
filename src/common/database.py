"""Database connection and helper functions for WikiSeed."""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get database connection with proper configuration.

    Args:
        db_path: Path to database file (default: from DATABASE_PATH env var)

    Returns:
        SQLite connection

    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    if db_path is None:
        db_path = os.getenv("DATABASE_PATH", "data/db/jobs.db")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries

    # Configure SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    return conn


def dict_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert SQLite Row to dictionary.

    Args:
        row: SQLite Row object

    Returns:
        Dictionary of column: value
    """
    return dict(row)


def execute_query(
    conn: sqlite3.Connection,
    query: str,
    params: tuple | Dict[str, Any] = (),
) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dictionaries.

    Args:
        conn: Database connection
        query: SQL query
        params: Query parameters

    Returns:
        List of result rows as dictionaries
    """
    cursor = conn.execute(query, params)
    return [dict_from_row(row) for row in cursor.fetchall()]


def get_system_state(conn: sqlite3.Connection, key: str) -> Optional[str]:
    """Get system state value by key.

    Args:
        conn: Database connection
        key: State key

    Returns:
        State value or None if not found
    """
    cursor = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else None


def set_system_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set system state value.

    Args:
        conn: Database connection
        key: State key
        value: State value
    """
    conn.execute(
        """
        INSERT INTO system_state (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )
    conn.commit()
