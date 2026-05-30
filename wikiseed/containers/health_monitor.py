"""Health monitor — polls public trackers for swarm health.

Timer-driven; runs every HEALTH_POLL_INTERVAL_SECONDS (6h per design).

For every torrent in the database:

1. Issues a UDP scrape (BEP-15) to every tracker in
   wikiseed.trackers.PUBLIC_TRACKERS. Trackers that time out or send
   garbage are treated as "unknown" — they neither pull the seeder count
   down nor make us think we're worse off than we are.
2. The torrent's effective seeder count is the max across all reachable
   trackers (conservative: best-known view of the swarm).
3. Updates torrents.seeder_count + last_seeder_check + health_status +
   below_threshold_since + eligible_for_deletion accordingly.
4. Appends a row to health_events on each transition between healthy and
   warning so the dashboard has an audit trail.
5. If a torrent has been below threshold for HEALTH_BELOW_THRESHOLD_HOURS
   continuous hours AND its local files have been deleted, enqueues a
   `redownload` job (the downloader fetches from ia_url back to the
   staging dir so qBittorrent can resume seeding).

Tracker reachability rule (per design): if every tracker is unreachable
we set health_status='unknown' without touching below_threshold_since,
so a tracker outage doesn't fake a swarm failure.
"""
import logging
import random
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.trackers import PUBLIC_TRACKERS

logger = logging.getLogger("health_monitor")

HEALTH_POLL_INTERVAL_SECONDS = 6 * 60 * 60

# BEP-15 fields.
UDP_PROTOCOL_MAGIC = 0x41727101980
UDP_ACTION_CONNECT = 0
UDP_ACTION_SCRAPE = 2
UDP_TIMEOUT_SECONDS = 5.0
# A single UDP packet carries at most ~74 info hashes (15 bytes header +
# 20 bytes per hash, target ~1500 byte MTU). Use a conservative batch.
UDP_SCRAPE_BATCH = 70


def _udp_scrape(tracker_url: str, info_hashes: list) -> Optional[dict]:
    """Returns {info_hash_bytes: (seeders, completed, leechers)} or None if
    the tracker is unreachable / responds with garbage."""
    parsed = urlparse(tracker_url)
    host, port = parsed.hostname, parsed.port
    if not host or not port:
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT_SECONDS)
    try:
        tid = random.randint(0, 2**32 - 1)
        sock.sendto(struct.pack(">QII", UDP_PROTOCOL_MAGIC, UDP_ACTION_CONNECT, tid),
                    (host, port))
        data, _ = sock.recvfrom(4096)
        if len(data) < 16:
            return None
        action, rtid, connection_id = struct.unpack(">IIQ", data[:16])
        if action != UDP_ACTION_CONNECT or rtid != tid:
            return None

        tid = random.randint(0, 2**32 - 1)
        body = struct.pack(">QII", connection_id, UDP_ACTION_SCRAPE, tid)
        for h in info_hashes:
            body += h
        sock.sendto(body, (host, port))
        data, _ = sock.recvfrom(8 + 12 * len(info_hashes) + 64)
        if len(data) < 8:
            return None
        action, rtid = struct.unpack(">II", data[:8])
        if action != UDP_ACTION_SCRAPE or rtid != tid:
            return None

        out = {}
        for i, h in enumerate(info_hashes):
            off = 8 + i * 12
            if off + 12 > len(data):
                break
            seeders, completed, leechers = struct.unpack(">III", data[off:off + 12])
            out[h] = (seeders, completed, leechers)
        return out
    except (OSError, struct.error):
        return None
    finally:
        sock.close()


def _scrape_all_trackers(info_hashes: list) -> dict:
    """Queries every tracker for the given info hashes in parallel.

    Returns {info_hash_bytes: best_seeder_count or None}. None means every
    tracker was unreachable for that hash."""
    by_hash: dict = {h: None for h in info_hashes}
    reachable_for_hash: dict = {h: False for h in info_hashes}

    def query(tracker):
        results: dict = {}
        for i in range(0, len(info_hashes), UDP_SCRAPE_BATCH):
            batch = info_hashes[i:i + UDP_SCRAPE_BATCH]
            partial = _udp_scrape(tracker, batch)
            if partial:
                results.update(partial)
        return tracker, results

    with ThreadPoolExecutor(max_workers=8) as pool:
        for fut in as_completed([pool.submit(query, t) for t in PUBLIC_TRACKERS]):
            tracker, results = fut.result()
            if not results:
                logger.debug("tracker %s unreachable for this batch", tracker)
                continue
            for h, (seeders, _, _) in results.items():
                reachable_for_hash[h] = True
                if by_hash[h] is None or seeders > by_hash[h]:
                    by_hash[h] = seeders

    # If no tracker responded for a given hash, keep None (unknown).
    return {h: (by_hash[h] if reachable_for_hash[h] else None)
            for h in info_hashes}


def _all_torrents() -> list:
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT id, torrent_name, info_hash, health_status,
                      below_threshold_since, ia_confirmed,
                      local_files_deleted_at
               FROM torrents
               WHERE info_hash IS NOT NULL"""
        )
        return [dict(r) for r in cur.fetchall()]


def _apply_health_update(t: dict, max_seeders: Optional[int]) -> None:
    """Persists the new health state and emits transition events."""
    threshold = CONFIG.health_min_seeders
    prev_status = t["health_status"]

    if max_seeders is None:
        # All trackers unreachable for this hash; don't touch
        # below_threshold_since, just mark unknown and leave the rest.
        with db_cursor() as cur:
            cur.execute(
                """UPDATE torrents SET
                       last_seeder_check = NOW(),
                       health_status = 'unknown'
                   WHERE id = %s""",
                (t["id"],),
            )
        return

    if max_seeders >= threshold:
        new_status = "healthy"
        with db_cursor() as cur:
            cur.execute(
                """UPDATE torrents SET
                       seeder_count = %s,
                       last_seeder_check = NOW(),
                       health_status = %s,
                       below_threshold_since = NULL,
                       eligible_for_deletion = (ia_confirmed = TRUE)
                   WHERE id = %s""",
                (max_seeders, new_status, t["id"]),
            )
        if prev_status in ("warning", "recovering"):
            _log_event(t["id"], "recovered", max_seeders,
                       f"seeders recovered above threshold ({max_seeders} >= {threshold})")
        return

    # Below threshold.
    new_status = "warning"
    with db_cursor() as cur:
        cur.execute(
            """UPDATE torrents SET
                   seeder_count = %s,
                   last_seeder_check = NOW(),
                   health_status = %s,
                   below_threshold_since = COALESCE(below_threshold_since, NOW()),
                   eligible_for_deletion = FALSE
               WHERE id = %s""",
            (max_seeders, new_status, t["id"]),
        )
    if prev_status not in ("warning", "recovering"):
        _log_event(t["id"], "below_threshold", max_seeders,
                   f"seeders below threshold ({max_seeders} < {threshold})")


def _log_event(torrent_id: int, event_type: str, seeder_count: Optional[int],
               notes: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO health_events (torrent_id, event_type, seeder_count, notes)
               VALUES (%s, %s, %s, %s)""",
            (torrent_id, event_type, seeder_count, notes),
        )


def _trigger_redownloads() -> None:
    """Enqueues redownload jobs for torrents whose swarm has stayed below
    threshold long enough AND whose local files were dropped earlier."""
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT id, torrent_name, seeder_count
               FROM torrents
               WHERE health_status = 'warning'
                 AND below_threshold_since IS NOT NULL
                 AND below_threshold_since <= NOW() - (%s || ' hours')::interval
                 AND local_files_deleted_at IS NOT NULL""",
            (CONFIG.health_below_threshold_hours,),
        )
        candidates = [dict(r) for r in cur.fetchall()]

    for t in candidates:
        jobs.enqueue("redownload", {"torrent_id": t["id"]})
        with db_cursor() as cur:
            cur.execute(
                "UPDATE torrents SET health_status='recovering' WHERE id=%s",
                (t["id"],),
            )
        _log_event(t["id"], "redownload_triggered", t["seeder_count"],
                   f"below threshold for >= {CONFIG.health_below_threshold_hours}h, "
                   "fetching from IA webseed")
        logger.info("triggered redownload for %s (id=%d)", t["torrent_name"], t["id"])


def poll_all_torrents() -> None:
    torrents = _all_torrents()
    if not torrents:
        logger.info("no torrents to poll")
        return

    info_hash_bytes = {}
    for t in torrents:
        try:
            info_hash_bytes[t["id"]] = bytes.fromhex(t["info_hash"])
        except ValueError:
            logger.warning("torrent %d has malformed info_hash, skipping", t["id"])

    if not info_hash_bytes:
        return

    hashes = list(info_hash_bytes.values())
    seeder_counts = _scrape_all_trackers(hashes)

    by_id_seeders = {}
    for tid, h in info_hash_bytes.items():
        by_id_seeders[tid] = seeder_counts.get(h)

    reachable = sum(1 for v in by_id_seeders.values() if v is not None)
    logger.info("polled %d torrents across %d trackers; %d had reachable trackers",
                len(by_id_seeders), len(PUBLIC_TRACKERS), reachable)

    for t in torrents:
        if t["id"] in by_id_seeders:
            _apply_health_update(t, by_id_seeders[t["id"]])

    _trigger_redownloads()


def main() -> None:
    setup("health_monitor")
    logger.info("health_monitor started, poll interval %d seconds, threshold %d seeders",
                HEALTH_POLL_INTERVAL_SECONDS, CONFIG.health_min_seeders)
    while True:
        try:
            poll_all_torrents()
        except Exception:
            logger.exception("tracker poll cycle failed")
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
