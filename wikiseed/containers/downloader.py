"""Downloader — processes 'download' jobs.

Reads a dump_id from the job payload, downloads the file from the Wikimedia
URL with HTTP Range resume support, computes sha256, validates against
the Wikimedia hash for XML or the ZIM magic bytes for ZIM, writes the
final hash + size to dumps, and enqueues an upload_to_ia job.

On hash mismatch the partial file is removed so the next retry starts clean.
"""
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.paths import canonical_download_path

logger = logging.getLogger("downloader")

CHUNK_SIZE = 4 * 1024 * 1024
POLL_INTERVAL_SECONDS = 10

# ZIM v5/v6 files start with these magic bytes; useful as a structural sanity
# check since Wikimedia publishes no upstream hash for ZIM.
ZIM_MAGIC = b"ZIM\x04"


def _load_dump(dump_id: int) -> Optional[dict]:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT * FROM dumps WHERE id=%s", (dump_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _set_status(dump_id: int, status: str) -> None:
    with db_cursor() as cur:
        cur.execute("UPDATE dumps SET download_status=%s WHERE id=%s", (status, dump_id))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def download(dump_id: int) -> None:
    dump = _load_dump(dump_id)
    if dump is None:
        raise RuntimeError(f"dump {dump_id} not found")
    if dump["download_status"] == "completed":
        logger.info("dump %d already complete, skipping", dump_id)
        return

    dest = canonical_download_path(dump)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _set_status(dump_id, "downloading")

    resume = dest.stat().st_size if dest.exists() else 0
    headers = {"User-Agent": CONFIG.user_agent}
    mode = "wb"
    if resume:
        headers["Range"] = f"bytes={resume}-"
        mode = "ab"
        logger.info("resuming %s at %d bytes", dest.name, resume)

    with requests.get(dump["wikimedia_url"], headers=headers, stream=True, timeout=(60, 600)) as r:
        if resume and r.status_code != 206:
            logger.warning("server ignored Range header for %s, restarting", dest.name)
            r.close()
            dest.unlink(missing_ok=True)
            return download(dump_id)
        r.raise_for_status()
        with open(dest, mode) as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)

    sha = _sha256_file(dest)
    size = dest.stat().st_size

    if dump["source_type"] in ("xml_current", "xml_history"):
        expected = dump["sha256_wikimedia"]
        if expected and sha != expected:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"sha256 mismatch for {dest.name}: expected {expected}, got {sha}"
            )
    else:
        with open(dest, "rb") as f:
            magic = f.read(4)
        if magic != ZIM_MAGIC:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"zim magic bytes missing for {dest.name}: got {magic!r}"
            )

    with db_cursor() as cur:
        cur.execute(
            """UPDATE dumps SET
                download_status='completed', download_completed_at=NOW(),
                sha256_wikiseed=%s, filesize_bytes=%s
               WHERE id=%s""",
            (sha, size, dump_id),
        )
    logger.info("downloaded dump %d (%s, %d bytes)", dump_id, dest.name, size)

    jobs.enqueue("upload_to_ia", {"dump_id": dump_id})


def main() -> None:
    setup("downloader")
    logger.info("downloader started")
    while True:
        job = jobs.claim(["download"])
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        dump_id = job["payload"].get("dump_id")
        try:
            download(dump_id)
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("download job %d (dump %s) failed", job["id"], dump_id)
            jobs.fail(job["id"], str(e))
            if dump_id is not None:
                try:
                    _set_status(dump_id, "failed")
                except Exception:
                    logger.exception("could not update dump status to failed")


if __name__ == "__main__":
    main()
