"""Creator — builds .torrent files from completed dumps.

Listens for: create_torrent

Stub. When implementing:

- Trigger by a watcher (in controller, or polling here) that detects when
  every dump in a group has download_status='completed' AND ia_confirmed=true.
  Groups per design:
    * xml_current/xml_history: by project + period (all language wikis combined)
    * zim: by project + scope + period (all languages combined)
- Generate SOURCES.json (see design doc schema) from dumps rows.
- Render README.txt / LICENSE.txt / VERSION.txt from wikiseed/templates/.
  XML and ZIM use different README templates.
- Build the .torrent with trackers from wikiseed.trackers.PUBLIC_TRACKERS
  and webseed URLs from each dump's ia_url.
- Insert a row in torrents, link via torrent_dumps, and enqueue:
    register_torrent  -> seeder
    publish_manifest  -> publisher
"""
import logging
import time

from wikiseed import jobs
from wikiseed.logging_setup import setup

logger = logging.getLogger("creator")

POLL_INTERVAL_SECONDS = 30


def create_torrent(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("creator.create_torrent is not yet implemented")


def main() -> None:
    setup("creator")
    logger.info("creator started (stub)")
    while True:
        job = jobs.claim(["create_torrent"])
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            create_torrent(job["payload"])
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("create_torrent failed")
            jobs.fail(job["id"], str(e), retry=False)


if __name__ == "__main__":
    main()
