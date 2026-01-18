"""Pytest configuration and fixtures for WikiSeed tests."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create temporary database for testing.

    Yields:
        Path to temporary database file
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)
    # Also remove WAL and SHM files
    Path(str(db_path) + "-wal").unlink(missing_ok=True)
    Path(str(db_path) + "-shm").unlink(missing_ok=True)


@pytest.fixture
def db_connection(temp_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Create database connection with test schema.

    Args:
        temp_db: Temporary database path

    Yields:
        Database connection
    """
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row

    # Configure SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    # Load schema
    schema_path = Path(__file__).parent.parent / "migrations" / "001_initial.sql"
    with open(schema_path) as f:
        conn.executescript(f.read())

    yield conn

    conn.close()


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing.

    Returns:
        Configuration dictionary
    """
    return {
        "wikiseed": {
            "storage": {
                "max_storage_gb": 100,
                "cleanup_threshold_pct": 85,
            },
            "download": {
                "max_retries": 5,
                "chunk_size_mb": 100,
            },
        }
    }
