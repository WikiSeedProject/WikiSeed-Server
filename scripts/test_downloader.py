#!/usr/bin/env python3
"""Test the downloader by downloading a single small file."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "jobs.db"


def test_download() -> None:
    """Set one small download job to pending and let downloader process it."""

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Find the smallest pending download job
        cursor = conn.execute(
            """
            SELECT d.id as dump_id, d.wiki_db_name, d.filename, d.size_bytes, j.id as job_id
            FROM dumps d
            JOIN jobs j ON j.dump_id = d.id
            WHERE j.job_type = 'download_dump'
              AND j.status = 'pending'
              AND d.size_bytes < 10000000
            ORDER BY d.size_bytes ASC
            LIMIT 1
            """
        )

        job = cursor.fetchone()
        if not job:
            print("No small pending download jobs found")
            sys.exit(1)

        job_id = job["job_id"]
        dump_id = job["dump_id"]
        filename = job["filename"]
        size = job["size_bytes"]

        print(f"Found test job:")
        print(f"  Job ID: {job_id}")
        print(f"  Dump ID: {dump_id}")
        print(f"  File: {filename}")
        print(f"  Size: {size:,} bytes ({size / 1024 / 1024:.2f} MB)")
        print()
        print("To test download:")
        print("  docker compose up downloader")
        print()
        print("To watch progress:")
        print("  docker compose logs -f downloader")
        print()
        print(f"To check if downloaded:")
        print(f"  ls -lh data/dumps/{filename}")

    finally:
        conn.close()


if __name__ == "__main__":
    test_download()
