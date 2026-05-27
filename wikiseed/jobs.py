"""Postgres-backed job queue.

Workers compete safely via SELECT ... FOR UPDATE SKIP LOCKED, so multiple
container replicas of the same worker can run without coordination.
"""
import logging
from typing import Optional

import psycopg2.extras

from wikiseed.db import connect

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3


def enqueue(job_type: str, payload: Optional[dict] = None) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO jobs (job_type, payload) VALUES (%s, %s) RETURNING id",
                (job_type, psycopg2.extras.Json(payload or {})),
            )
            job_id = cur.fetchone()[0]
        conn.commit()
    logger.info("enqueued %s id=%d", job_type, job_id)
    return job_id


def claim(job_types: list) -> Optional[dict]:
    """Atomically marks the oldest pending job of one of the given types as
    running and returns it. Returns None if nothing is pending."""
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE jobs SET status = 'running', started_at = NOW()
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status = 'pending' AND job_type = ANY(%s)
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, job_type, payload, retry_count
                """,
                (list(job_types),),
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


def complete(job_id: int) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status='completed', completed_at=NOW() WHERE id=%s",
                (job_id,),
            )
        conn.commit()


def fail(job_id: int, error: str, retry: bool = True, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
    """If retry=True, the job is reset to pending until retry_count hits
    max_retries, then marked failed."""
    with connect() as conn:
        with conn.cursor() as cur:
            if retry:
                cur.execute(
                    """
                    UPDATE jobs SET
                        status = CASE WHEN retry_count + 1 >= %s THEN 'failed' ELSE 'pending' END,
                        retry_count = retry_count + 1,
                        last_error = %s,
                        started_at = NULL
                    WHERE id = %s
                    """,
                    (max_retries, error, job_id),
                )
            else:
                cur.execute(
                    "UPDATE jobs SET status='failed', last_error=%s, completed_at=NOW() WHERE id=%s",
                    (error, job_id),
                )
        conn.commit()
