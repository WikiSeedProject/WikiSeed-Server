"""Uploader — uploads each dump file to Internet Archive.

Listens for: upload_to_ia

Stub. When implementing:

- Use the `internetarchive` Python library.
  ia.upload(identifier, files=[local_path], metadata=..., access_key=..., secret_key=...)
- One IA item per dump file. Identifier convention from design doc:
    wikiseed-{wiki}-current-{YYYY-MM}
    wikiseed-{wiki}-history-{YYYY-MM}
    wikiseed-zim-{project}-{lang}-{scope}-{YYYY-MM}
- Item metadata should include: title, creator (Wikimedia contributors),
  mediatype (data/web), licenseurl, source URL, subject tags.
- After successful upload, set dumps.ia_item_id, dumps.ia_url, dumps.ia_confirmed_at
  and update torrents.ia_confirmed when every dump in a torrent's group is confirmed.
- Retry with exponential backoff on transient IA failures (the job queue
  already handles retries up to DEFAULT_MAX_RETRIES).
"""
import logging
import time

from wikiseed import jobs
from wikiseed.logging_setup import setup

logger = logging.getLogger("uploader")

POLL_INTERVAL_SECONDS = 30


def upload(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("uploader.upload is not yet implemented")


def main() -> None:
    setup("uploader")
    logger.info("uploader started (stub)")
    while True:
        job = jobs.claim(["upload_to_ia"])
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            upload(job["payload"])
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("upload_to_ia failed")
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
