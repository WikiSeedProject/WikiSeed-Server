"""Health monitor — polls public trackers and triggers redownloads.

Timer-driven; polls every 6 hours (per design).

Stub. When implementing:

- For each torrent (info_hash, NOT torrent_file_path), query every tracker in
  wikiseed.trackers.PUBLIC_TRACKERS using the UDP scrape protocol.
  Reference: BEP-15. There is no canonical pip library; either roll a small
  asyncio UDP scraper or use a lib like `py-bencode-scrape`.
- For each tracker: get (seeders, leechers, completed). Pick the max seeder
  count across all reachable trackers as the torrent's seeder count.
- If a tracker is unreachable, log it but do not let it pull the seeder count
  downward. Per design: 'treat seeder count as unknown'.
- Update torrents.seeder_count, last_seeder_check, health_status:
    seeder_count >= HEALTH_MIN_SEEDERS  -> 'healthy'
    seeder_count <  HEALTH_MIN_SEEDERS  -> 'warning'  (set below_threshold_since if NULL)
    all trackers unreachable            -> 'unknown' (do not change below_threshold_since)
- Compute eligible_for_deletion = ia_confirmed AND seeder_count >= HEALTH_MIN_SEEDERS.
- If below_threshold_since is older than HEALTH_BELOW_THRESHOLD_HOURS AND
  local_files_deleted_at IS NOT NULL: enqueue 'redownload' jobs (one per dump in
  the torrent), set health_status='recovering', append a 'redownload_triggered'
  row to health_events.
- Log every state transition to health_events.
"""
import logging
import time

from wikiseed.logging_setup import setup

logger = logging.getLogger("health_monitor")

POLL_INTERVAL_SECONDS = 6 * 60 * 60


def poll_all_torrents() -> None:
    # TODO: implement per docstring above.
    logger.info("poll_all_torrents not yet implemented")


def main() -> None:
    setup("health_monitor")
    logger.info("health_monitor started (stub)")
    while True:
        try:
            poll_all_torrents()
        except Exception:
            logger.exception("tracker poll failed")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
