"""Storage manager — enforces the HDD storage budget.

Timer-driven; runs hourly (per design).

Stub. When implementing:

- Measure used bytes under CONFIG.data_dir (shutil.disk_usage on the mount, or
  sum of dumps.filesize_bytes WHERE torrents.local_files_deleted_at IS NULL).
- If used > CONFIG.storage_budget_bytes, build a deletion candidate list:
    SELECT torrents WHERE eligible_for_deletion AND local_files_deleted_at IS NULL
    ORDER BY created_at ASC
  Walk it oldest-first, deleting until used <= budget (with some slack).
- For each chosen torrent:
    * mark torrents.local_files_deleted_at = NOW()
    * append a 'deleted' row to health_events
    * enqueue 'remove_local_payload' for the seeder
    * delete the dump files from disk (only after the DB row is updated, so
      we never end up with a torrent row that points at missing files but
      claims to still have them).
- Never delete the torrents row, the magnet_link, or the SOURCES.json reference
  — only the local payload. Recovery is via the IA webseed.
- Never delete a torrent that fails the IA-confirmed + seeders>=threshold check.
  The eligible_for_deletion flag enforces this; do not bypass it.
"""
import logging
import time

from wikiseed.logging_setup import setup

logger = logging.getLogger("storage_manager")

POLL_INTERVAL_SECONDS = 60 * 60


def check_storage() -> None:
    # TODO: implement per docstring above.
    logger.info("check_storage not yet implemented")


def main() -> None:
    setup("storage_manager")
    logger.info("storage_manager started (stub)")
    while True:
        try:
            check_storage()
        except Exception:
            logger.exception("storage check failed")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
