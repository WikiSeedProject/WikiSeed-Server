"""Seeder — manages the local qBittorrent via its Web API.

Listens for:
    register_torrent      - add a freshly-built .torrent to qBittorrent
                            and start seeding from the staging directory
    remove_local_payload  - tell qBittorrent to forget the torrent so it
                            stops trying to seed files the storage
                            manager has already removed

`remove_local_payload` passes delete_files=False because the storage
manager has already deleted the staging directory by the time this job
runs. The torrent row, magnet link, and info hash are preserved in the
database so the health monitor keeps tracking the swarm.
"""
import logging
import time

import qbittorrentapi as qbt

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.paths import qbittorrent_save_path, torrent_file_path

logger = logging.getLogger("seeder")

POLL_INTERVAL_SECONDS = 30

# All WikiSeed-managed torrents go under this category/tag so admins can
# filter them in the qBittorrent UI.
CATEGORY = "wikiseed"


def _client() -> qbt.Client:
    c = qbt.Client(
        host=CONFIG.qbittorrent_host,
        port=CONFIG.qbittorrent_port,
        username=CONFIG.qbittorrent_user,
        password=CONFIG.qbittorrent_password,
        REQUESTS_ARGS={"timeout": 30},
    )
    c.auth_log_in()
    return c


def _load_torrent_row(torrent_id: int) -> dict:
    with db_cursor(commit=False) as cur:
        cur.execute(
            "SELECT torrent_name, info_hash FROM torrents WHERE id=%s",
            (torrent_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"torrent {torrent_id} not found")
        return dict(row)


def register_torrent(payload: dict) -> None:
    torrent_id = payload["torrent_id"]
    t = _load_torrent_row(torrent_id)
    local_torrent = torrent_file_path(t["torrent_name"])
    if not local_torrent.exists():
        raise RuntimeError(f".torrent file missing: {local_torrent}")

    c = _client()
    with open(local_torrent, "rb") as f:
        result = c.torrents_add(
            torrent_files=f.read(),
            save_path=str(qbittorrent_save_path()),
            is_paused=False,
            use_auto_torrent_management=False,
            category=CATEGORY,
            tags=CATEGORY,
        )
    # qBittorrent's API returns "Ok." on success regardless of whether the
    # torrent was already known, so re-adds are harmless.
    if result != "Ok.":
        raise RuntimeError(
            f"qBittorrent rejected {t['torrent_name']}: {result!r}"
        )
    logger.info("registered %s in qBittorrent (torrent_id=%d)",
                t["torrent_name"], torrent_id)


def remove_local_payload(payload: dict) -> None:
    torrent_id = payload["torrent_id"]
    t = _load_torrent_row(torrent_id)
    if not t["info_hash"]:
        logger.info("torrent %d has no info_hash, nothing to remove", torrent_id)
        return
    c = _client()
    c.torrents_delete(torrent_hashes=t["info_hash"], delete_files=False)
    logger.info("removed %s from qBittorrent (info_hash=%s)",
                t["torrent_name"], t["info_hash"])


HANDLERS = {
    "register_torrent": register_torrent,
    "remove_local_payload": remove_local_payload,
}


def main() -> None:
    setup("seeder")
    logger.info("seeder started")
    while True:
        job = jobs.claim(list(HANDLERS.keys()))
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            HANDLERS[job["job_type"]](job["payload"])
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("%s failed", job["job_type"])
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
