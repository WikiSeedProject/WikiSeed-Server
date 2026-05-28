"""Thin psycopg2 helpers. Every call opens a new connection — fine for the
low-QPS controller/worker pattern and avoids pool lifecycle bugs across
short-lived job processing."""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from wikiseed.config import CONFIG


def connect():
    return psycopg2.connect(
        host=CONFIG.pg_host,
        port=CONFIG.pg_port,
        dbname=CONFIG.pg_db,
        user=CONFIG.pg_user,
        password=CONFIG.pg_password,
    )


@contextmanager
def cursor(commit: bool = True):
    """Yields a RealDictCursor and handles commit/rollback/close."""
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
