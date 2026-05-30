"""Uploader — uploads each completed dump to Internet Archive.

Listens for: upload_to_ia

One IA item per dump file, identifier deterministic from the dump row:

    xml_current : wikiseed-{wiki}-current-{YYYY-MM}
    xml_history : wikiseed-{wiki}-history-{YYYY-MM}
    zim         : wikiseed-zim-{project}-{lang}-{scope}-{YYYY-MM}

After a successful upload, sets dumps.ia_item_id / ia_url / ia_confirmed_at
and, if every dump in the same torrent group is IA-confirmed, enqueues
create_torrent for the creator to bundle them.
"""
import logging
import time
from pathlib import Path
from typing import Optional

import internetarchive as ia

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.paths import canonical_download_path
from wikiseed.projects import project_from_wiki

logger = logging.getLogger("uploader")

POLL_INTERVAL_SECONDS = 30


def _ia_identifier(dump: dict) -> str:
    if dump["source_type"] == "xml_current":
        return f"wikiseed-{dump['wiki_or_project']}-current-{dump['period']}"
    if dump["source_type"] == "xml_history":
        return f"wikiseed-{dump['wiki_or_project']}-history-{dump['period']}"
    return (f"wikiseed-zim-{dump['wiki_or_project']}-"
            f"{dump['language']}-{dump['zim_scope']}-{dump['period']}")


def _ia_url(identifier: str, filename: str) -> str:
    return f"https://archive.org/download/{identifier}/{filename}"


def _ia_metadata(dump: dict) -> dict:
    """Minimal IA metadata. Customize/extend as needed."""
    if dump["source_type"] in ("xml_current", "xml_history"):
        kind = "Current" if dump["source_type"] == "xml_current" else "History"
        title = f"WikiSeed — {dump['wiki_or_project']} XML {kind} Export — {dump['period']}"
        subject = f"wikiseed;wikimedia;mediawiki;xml;{dump['wiki_or_project']}"
    else:
        scope = (dump["zim_scope"] or "").capitalize()
        title = (f"WikiSeed — {dump['wiki_or_project']} ZIM {scope} "
                 f"({dump['language']}) — {dump['period']}")
        subject = (f"wikiseed;wikimedia;kiwix;zim;"
                   f"{dump['wiki_or_project']};{dump['language']};{dump['zim_scope']}")
    return {
        "title": title,
        "creator": "Wikimedia Foundation contributors",
        "mediatype": "web",
        "collection": "opensource",
        "licenseurl": "https://creativecommons.org/licenses/by-sa/4.0/",
        "subject": subject,
        "description": (
            f"Mirror of {dump['wikimedia_url']} preserved by WikiSeed. "
            "See https://wikiseed.app."
        ),
        "originalurl": dump["wikimedia_url"],
        "source": dump["wikimedia_url"],
    }


def _load_dump(dump_id: int) -> Optional[dict]:
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT * FROM dumps WHERE id=%s", (dump_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def upload(payload: dict) -> None:
    dump_id = payload["dump_id"]
    dump = _load_dump(dump_id)
    if dump is None:
        raise RuntimeError(f"dump {dump_id} not found")
    if dump["download_status"] != "completed":
        raise RuntimeError(
            f"dump {dump_id} is not downloaded (status={dump['download_status']})"
        )
    if dump["ia_confirmed_at"]:
        logger.info("dump %d already IA-confirmed, skipping", dump_id)
        _check_and_dispatch_group(dump)
        return
    if not (CONFIG.ia_access_key and CONFIG.ia_secret_key):
        raise RuntimeError("IA credentials missing (IA_ACCESS_KEY / IA_SECRET_KEY)")

    local = canonical_download_path(dump)
    if not local.exists():
        raise RuntimeError(f"local file missing for dump {dump_id}: {local}")

    identifier = _ia_identifier(dump)
    filename = local.name
    metadata = _ia_metadata(dump)

    logger.info("uploading dump %d to IA item %s (%s)", dump_id, identifier, filename)
    responses = ia.upload(
        identifier=identifier,
        files=[str(local)],
        metadata=metadata,
        access_key=CONFIG.ia_access_key,
        secret_key=CONFIG.ia_secret_key,
        retries=5,
        verify=True,
    )
    for r in responses:
        status = getattr(r, "status_code", None)
        if status not in (200, 201):
            raise RuntimeError(f"IA upload returned status {status}")

    ia_url = _ia_url(identifier, filename)
    with db_cursor() as cur:
        cur.execute(
            """UPDATE dumps SET ia_item_id=%s, ia_url=%s, ia_confirmed_at=NOW()
               WHERE id=%s""",
            (identifier, ia_url, dump_id),
        )
        # Reload so the group check sees ia_confirmed_at for THIS row.
        cur.execute("SELECT * FROM dumps WHERE id=%s", (dump_id,))
        dump = dict(cur.fetchone())
    logger.info("IA-confirmed dump %d: %s", dump_id, ia_url)

    _check_and_dispatch_group(dump)


def _check_and_dispatch_group(dump: dict) -> None:
    """If every dump in this dump's torrent group is IA-confirmed, enqueue
    create_torrent. The creator must be idempotent on torrent_name since
    two uploaders finishing concurrently may both reach this point."""
    if dump["source_type"] in ("xml_current", "xml_history"):
        # XML groups by project x period across all language wikis.
        project = project_from_wiki(dump["wiki_or_project"])
        with db_cursor(commit=False) as cur:
            cur.execute(
                """SELECT wiki_or_project, ia_confirmed_at
                   FROM dumps
                   WHERE source_type = %s
                     AND period = %s
                     AND download_status = 'completed'""",
                (dump["source_type"], dump["period"]),
            )
            rows = [dict(r) for r in cur.fetchall()]
        in_group = [r for r in rows if project_from_wiki(r["wiki_or_project"]) == project]
        key = {"source_type": dump["source_type"], "project": project, "period": dump["period"]}
    else:
        with db_cursor(commit=False) as cur:
            cur.execute(
                """SELECT ia_confirmed_at
                   FROM dumps
                   WHERE source_type = 'zim'
                     AND wiki_or_project = %s
                     AND zim_scope = %s
                     AND period = %s
                     AND download_status = 'completed'""",
                (dump["wiki_or_project"], dump["zim_scope"], dump["period"]),
            )
            in_group = [dict(r) for r in cur.fetchall()]
        key = {
            "source_type": "zim",
            "project": dump["wiki_or_project"],
            "zim_scope": dump["zim_scope"],
            "period": dump["period"],
        }

    total = len(in_group)
    confirmed = sum(1 for r in in_group if r["ia_confirmed_at"] is not None)
    if total == 0:
        return
    if total == confirmed:
        logger.info("group %s complete (%d files), enqueueing create_torrent",
                    key, confirmed)
        jobs.enqueue("create_torrent", key)
    else:
        logger.debug("group %s: %d/%d confirmed, waiting", key, confirmed, total)


HANDLERS = {
    "upload_to_ia": upload,
}


def main() -> None:
    setup("uploader")
    logger.info("uploader started")
    while True:
        job = jobs.claim(list(HANDLERS.keys()))
        if not job:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            HANDLERS[job["job_type"]](job["payload"])
            jobs.complete(job["id"])
        except Exception as e:
            logger.exception("upload_to_ia failed")
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
