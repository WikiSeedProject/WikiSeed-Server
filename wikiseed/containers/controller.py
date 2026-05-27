"""Controller — runs the calendar scheduler.

Wakes up periodically and enqueues scrape, manifest, and status jobs
according to the schedule from the design doc:

- scrape_xml_current: daily, 5th-25th of every month
- scrape_xml_history: daily, 5th-25th of January and July
- scrape_zim:         once on the 1st of every month
- publish_manifest:   hourly + after pipeline events (TODO event hooks)
- publish_status:     hourly

Last-run timestamps live in the scheduler_state table so the controller
is idempotent across restarts.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from wikiseed import jobs
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup

logger = logging.getLogger("controller")

TICK_INTERVAL_SECONDS = 60


def _last_run(task: str) -> Optional[datetime]:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT last_run FROM scheduler_state WHERE task=%s", (task,))
        row = cur.fetchone()
        return row["last_run"] if row else None


def _mark_run(task: str, now: datetime) -> None:
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO scheduler_state (task, last_run) VALUES (%s, %s)
               ON CONFLICT (task) DO UPDATE SET last_run = EXCLUDED.last_run""",
            (task, now),
        )


def _due_daily(task: str, now: datetime) -> bool:
    last = _last_run(task)
    return last is None or last.date() != now.date()


def _due_hourly(task: str, now: datetime) -> bool:
    last = _last_run(task)
    return last is None or (now - last).total_seconds() >= 3600


def tick() -> None:
    now = datetime.now(timezone.utc)
    day = now.day
    month = now.month

    if 5 <= day <= 25 and _due_daily("scrape_xml_current", now):
        jobs.enqueue("scrape_xml_current")
        _mark_run("scrape_xml_current", now)

    if month in (1, 7) and 5 <= day <= 25 and _due_daily("scrape_xml_history", now):
        jobs.enqueue("scrape_xml_history")
        _mark_run("scrape_xml_history", now)

    if day == 1 and _due_daily("scrape_zim", now):
        jobs.enqueue("scrape_zim")
        _mark_run("scrape_zim", now)

    if _due_hourly("publish_manifest", now):
        jobs.enqueue("publish_manifest")
        _mark_run("publish_manifest", now)

    if _due_hourly("publish_status", now):
        jobs.enqueue("publish_status")
        _mark_run("publish_status", now)


def main() -> None:
    setup("controller")
    logger.info("controller started")
    while True:
        try:
            tick()
        except Exception:
            logger.exception("tick failed")
        time.sleep(TICK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
