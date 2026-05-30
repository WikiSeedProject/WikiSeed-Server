"""Downloader — fetches files for the pipeline.

Handles two job types:

    download    Initial fetch of a dump from its Wikimedia URL. Writes to
                the canonical download path, verifies sha256 against the
                Wikimedia hash (XML) or the ZIM magic bytes (ZIM),
                records the WikiSeed sha + size, and enqueues upload_to_ia.

    redownload  Recovery fetch of every dump in a torrent from its IA URL.
                Writes directly to the torrent's staging dir, verifies
                sha256 against sha256_wikiseed, clears
                torrents.local_files_deleted_at, and enqueues
                register_torrent so qBittorrent picks it back up. README/
                LICENSE/VERSION/SOURCES are NOT re-rendered here — qBittorrent
                may flag them as missing until the creator (or a future
                recovery job) rebuilds them. TODO.

Hash mismatches remove the partial file so the next retry starts clean.
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
from wikiseed.paths import canonical_download_path, torrent_staging_dir

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


def _http_download_with_resume(url: str, dest: Path) -> None:
    """Streams `url` to `dest` using a Range request when `dest` partially
    exists. On Range-not-honored, restarts from zero exactly once."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    resume = dest.stat().st_size if dest.exists() else 0
    headers = {"User-Agent": CONFIG.user_agent}
    mode = "wb"
    if resume:
        headers["Range"] = f"bytes={resume}-"
        mode = "ab"
        logger.info("resuming %s at %d bytes", dest.name, resume)
    with requests.get(url, headers=headers, stream=True, timeout=(60, 600)) as r:
        if resume and r.status_code != 206:
            logger.warning("server ignored Range for %s, restarting", dest.name)
            r.close()
            dest.unlink(missing_ok=True)
            return _http_download_with_resume(url, dest)
        r.raise_for_status()
        with open(dest, mode) as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)


def download(dump_id: int) -> None:
    dump = _load_dump(dump_id)
    if dump is None:
        raise RuntimeError(f"dump {dump_id} not found")
    if dump["download_status"] == "completed":
        logger.info("dump %d already complete, skipping", dump_id)
        return

    dest = canonical_download_path(dump)
    _set_status(dump_id, "downloading")
    _http_download_with_resume(dump["wikimedia_url"], dest)

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


def _load_torrent_for_redownload(torrent_id: int) -> tuple:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT torrent_name FROM torrents WHERE id=%s", (torrent_id,))
        t = cur.fetchone()
        if t is None:
            raise RuntimeError(f"torrent {torrent_id} not found")
        cur.execute(
            """SELECT d.* FROM dumps d
               JOIN torrent_dumps td ON td.dump_id = d.id
               WHERE td.torrent_id = %s""",
            (torrent_id,),
        )
        dumps = [dict(r) for r in cur.fetchall()]
    return t["torrent_name"], dumps


def redownload(payload: dict) -> None:
    torrent_id = payload["torrent_id"]
    torrent_name, dumps = _load_torrent_for_redownload(torrent_id)

    stage = torrent_staging_dir(torrent_name)
    stage.mkdir(parents=True, exist_ok=True)
    logger.info("redownloading %s (%d files) from IA webseed", torrent_name, len(dumps))

    for dump in dumps:
        if not dump["ia_url"]:
            raise RuntimeError(f"dump {dump['id']} has no IA URL; cannot redownload")
        dest = stage / Path(dump["wikimedia_url"]).name
        if dest.exists() and dest.stat().st_size == (dump["filesize_bytes"] or 0):
            continue  # already restored in a previous run
        _http_download_with_resume(dump["ia_url"], dest)
        sha = _sha256_file(dest)
        if sha != dump["sha256_wikiseed"]:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"sha256 mismatch on redownload of {dest.name}: "
                f"expected {dump['sha256_wikiseed']}, got {sha}"
            )

    with db_cursor() as cur:
        cur.execute(
            "UPDATE torrents SET local_files_deleted_at=NULL WHERE id=%s",
            (torrent_id,),
        )
    jobs.enqueue("register_torrent", {"torrent_id": torrent_id})
    logger.info("redownload complete for %s, re-registering with seeder", torrent_name)


def main() -> None:
    setup("downloader")
    logger.info("downloader started")
    while True:
        job = jobs.claim(["download", "redownload"])
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        try:
            if job["job_type"] == "download":
                dump_id = job["payload"]["dump_id"]
                try:
                    download(dump_id)
                except Exception:
                    try:
                        _set_status(dump_id, "failed")
                    except Exception:
                        logger.exception("could not update dump status to failed")
                    raise
            else:
                redownload(job["payload"])
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("%s job %d failed", job["job_type"], job["id"])
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
