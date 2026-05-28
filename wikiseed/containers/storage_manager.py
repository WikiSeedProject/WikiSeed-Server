"""Storage manager — enforces the HDD storage budget.

Timer-driven; runs every hour.

When disk usage on the data mount exceeds TARGET_USED_FRACTION of the
configured budget, deletes eligible torrents oldest-first until usage
falls back below the target. Eligibility is set by the health monitor
(`eligible_for_deletion = ia_confirmed AND seeder_count >= threshold`)
and is never bypassed here.

For each chosen torrent:

1. Mark `torrents.local_files_deleted_at = NOW()`. After this point no
   other worker (creator, publisher) treats the local files as present.
2. Append a `deleted` row to `health_events` for audit.
3. Enqueue `remove_local_payload` so the seeder can deregister it from
   qBittorrent (no-op while the seeder is a stub).
4. Unlink the dump files from disk.

The torrent row, magnet link, info hash, and torrent_dumps join rows are
kept — only the payload is gone. The health monitor keeps tracking it,
and if the swarm drops below threshold for the configured window, a
redownload from the IA webseed is triggered.
"""
import logging
import shutil
import time
from pathlib import Path

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup

logger = logging.getLogger("storage_manager")

POLL_INTERVAL_SECONDS = 60 * 60

# Trigger deletion once usage crosses this share of the budget; stop when
# back below it. Hysteresis (start = stop here) keeps us off the edge —
# tweak if churn is a problem.
TARGET_USED_FRACTION = 0.90


def disk_used_bytes() -> int:
    """Hardware-reported usage of the mount that holds CONFIG.data_dir.

    Includes any non-WikiSeed files on the same mount. Per the design,
    the HDD is dedicated to WikiSeed so this matches the budget intent.
    """
    return shutil.disk_usage(CONFIG.data_dir).used


def _local_path(dump: dict) -> Path:
    """Mirror of downloader._local_path — duplicated to avoid a cross-container
    import. If the directory layout changes, update both."""
    filename = Path(dump["wikimedia_url"]).name
    if dump["source_type"] == "xml_current":
        return CONFIG.data_dir / "xml_current" / dump["wiki_or_project"] / dump["period"] / filename
    if dump["source_type"] == "xml_history":
        return CONFIG.data_dir / "xml_history" / dump["wiki_or_project"] / dump["period"] / filename
    return CONFIG.data_dir / "zim" / dump["wiki_or_project"] / filename


def _select_eligible_oldest() -> list:
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT id, torrent_name, total_size_bytes, created_at
               FROM torrents
               WHERE eligible_for_deletion = TRUE
                 AND local_files_deleted_at IS NULL
               ORDER BY created_at ASC"""
        )
        return [dict(r) for r in cur.fetchall()]


def _torrent_dumps(torrent_id: int) -> list:
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT d.id, d.wikimedia_url, d.source_type,
                      d.wiki_or_project, d.period, d.zim_scope,
                      d.filesize_bytes
               FROM dumps d
               JOIN torrent_dumps td ON td.dump_id = d.id
               WHERE td.torrent_id = %s""",
            (torrent_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def drop_torrent(torrent: dict) -> int:
    """Delete one torrent's local payload. Returns bytes freed (0 if the
    torrent was already deleted by a concurrent worker)."""
    torrent_id = torrent["id"]

    # Atomic claim. Re-checks eligible_for_deletion in case the health
    # monitor revoked it after we read the candidate list; also serves as a
    # no-op if another worker already dropped this torrent.
    with db_cursor() as cur:
        cur.execute(
            """UPDATE torrents
               SET local_files_deleted_at = NOW()
               WHERE id = %s
                 AND local_files_deleted_at IS NULL
                 AND eligible_for_deletion = TRUE
               RETURNING id""",
            (torrent_id,),
        )
        if cur.fetchone() is None:
            logger.info("torrent %d no longer eligible or already dropped, skipping",
                        torrent_id)
            return 0

    dumps = _torrent_dumps(torrent_id)
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO health_events (torrent_id, event_type, notes)
               VALUES (%s, 'deleted', %s)""",
            (torrent_id, f"storage_manager dropped local payload ({len(dumps)} files)"),
        )

    jobs.enqueue("remove_local_payload", {"torrent_id": torrent_id})

    freed = 0
    for dump in dumps:
        path = _local_path(dump)
        try:
            if path.exists():
                size = path.stat().st_size
                path.unlink()
                freed += size
            else:
                logger.warning("expected file missing for dump %d: %s", dump["id"], path)
        except OSError as e:
            logger.warning("could not unlink %s: %s", path, e)

    logger.info("dropped torrent %d (%s): freed %d bytes from %d files",
                torrent_id, torrent["torrent_name"], freed, len(dumps))
    return freed


def check_storage() -> None:
    budget = CONFIG.storage_budget_bytes
    target = int(budget * TARGET_USED_FRACTION)
    used = disk_used_bytes()

    if used <= target:
        logger.info("storage ok: used=%d bytes (%.1f%% of budget)",
                    used, used / budget * 100)
        return

    logger.info("storage over target: used=%d, target=%d, need to free %d bytes",
                used, target, used - target)

    candidates = _select_eligible_oldest()
    if not candidates:
        logger.warning(
            "over budget but no eligible torrents to delete "
            "(eligibility requires ia_confirmed AND seeder_count >= %d)",
            CONFIG.health_min_seeders,
        )
        return

    freed = 0
    dropped = 0
    for torrent in candidates:
        if used - freed <= target:
            break
        try:
            freed += drop_torrent(torrent)
            dropped += 1
        except Exception:
            logger.exception("failed to drop torrent %d", torrent["id"])

    if used - freed > target:
        logger.warning(
            "exhausted eligible torrents (%d dropped, %d bytes freed) but "
            "still over target by %d bytes",
            dropped, freed, used - freed - target,
        )
    else:
        logger.info("freed %d bytes by dropping %d torrents", freed, dropped)


def main() -> None:
    setup("storage_manager")
    logger.info(
        "storage_manager started, budget=%d bytes, target=%.0f%% of budget",
        CONFIG.storage_budget_bytes, TARGET_USED_FRACTION * 100,
    )
    while True:
        try:
            check_storage()
        except Exception:
            logger.exception("storage check failed")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
