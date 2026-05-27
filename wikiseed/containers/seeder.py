"""Seeder — manages the local qBittorrent via its Web API.

Listens for: register_torrent, remove_local_payload

Stub. When implementing:

- Use `qbittorrent-api` library (qbittorrentapi.Client) configured via
  CONFIG.qbittorrent_host/port/user/password.
- register_torrent: client.torrents_add(torrent_files=..., save_path=..., is_paused=False)
- remove_local_payload: keep the torrent in qBittorrent's list (so the metadata
  is preserved) but delete the on-disk files. With qBittorrent API the cleanest
  pattern is: client.torrents_delete(delete_files=True, torrent_hashes=[hash])
  followed by re-adding a 'metadata only' record, OR simply unlinking the local
  files out-of-band and letting qBittorrent show errored status. Decide based on
  what behavior you want when seeders come back online and we need to redownload.
- The health monitor enqueues redownload jobs that the downloader will pick up;
  after files are local again, enqueue register_torrent here to resume seeding.
"""
import logging
import time

from wikiseed import jobs
from wikiseed.logging_setup import setup

logger = logging.getLogger("seeder")

POLL_INTERVAL_SECONDS = 30


def register_torrent(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("seeder.register_torrent is not yet implemented")


def remove_local_payload(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("seeder.remove_local_payload is not yet implemented")


HANDLERS = {
    "register_torrent": register_torrent,
    "remove_local_payload": remove_local_payload,
}


def main() -> None:
    setup("seeder")
    logger.info("seeder started (stub)")
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
