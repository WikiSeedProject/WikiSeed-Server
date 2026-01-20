#!/usr/bin/env python3
"""Create a test discover_wikis job for scraper testing."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "db" / "jobs.db"


def create_test_job(cycle_date: str | None = None, test_mode: bool = True, wikis: list[str] | None = None) -> None:
    """Create a test discover_wikis job.

    Args:
        cycle_date: Cycle date in YYYY-MM-DD format (default: next 20th or 1st)
        test_mode: If True, only process 5 wikis (default: True)
        wikis: Optional list of specific wikis to process
    """
    # Determine cycle date if not provided
    if cycle_date is None:
        today = datetime.now()
        # Use next cycle date (1st or 20th)
        if today.day < 20:
            cycle_date = today.replace(day=20).strftime("%Y-%m-%d")
        else:
            next_month = today.replace(day=1) + timedelta(days=32)
            cycle_date = next_month.replace(day=1).strftime("%Y-%m-%d")

    # Build job parameters
    params = {"test_mode": test_mode}
    if wikis:
        params["wikis"] = wikis

    # Check if database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Run this first: docker compose run --rm db-init")
        sys.exit(1)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Create the job
        cursor = conn.execute(
            """
            INSERT INTO jobs (job_type, status, cycle_date, params)
            VALUES (?, ?, ?, ?)
            """,
            ("discover_wikis", "pending", cycle_date, json.dumps(params)),
        )
        conn.commit()

        job_id = cursor.lastrowid

        print(f"✓ Created test job:")
        print(f"  Job ID: {job_id}")
        print(f"  Type: discover_wikis")
        print(f"  Cycle Date: {cycle_date}")
        print(f"  Test Mode: {test_mode}")
        if wikis:
            print(f"  Wikis: {', '.join(wikis)}")
        print()
        print("To run the scraper:")
        print("  docker compose up scraper")
        print()
        print("To watch logs:")
        print("  docker compose logs -f scraper")
        print()
        print("To check job status:")
        print(f"  sqlite3 {DB_PATH} \"SELECT * FROM jobs WHERE id = {job_id};\"")

    except Exception as e:
        print(f"Error creating job: {e}")
        sys.exit(1)

    finally:
        conn.close()


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Create a test discover_wikis job")
    parser.add_argument(
        "--cycle-date",
        help="Cycle date in YYYY-MM-DD format (default: next 1st or 20th)",
    )
    parser.add_argument(
        "--no-test-mode",
        action="store_true",
        help="Process all wikis instead of just 5",
    )
    parser.add_argument(
        "--wikis",
        nargs="+",
        help="Specific wikis to process (e.g., enwiki frwiki)",
    )

    args = parser.parse_args()

    create_test_job(
        cycle_date=args.cycle_date,
        test_mode=not args.no_test_mode,
        wikis=args.wikis,
    )


if __name__ == "__main__":
    main()
