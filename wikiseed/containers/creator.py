"""Creator — builds .torrent files from completed dump groups.

Listens for: create_torrent (payload describes the group)

For each group:

1. Resolves all dump rows belonging to the group. Every dump must be
   download-complete and IA-confirmed before we bundle.
2. Stages the torrent directory at
   {data_dir}/torrents/{torrent_name}/ by moving each dump's file from
   its canonical location, then renders README/LICENSE/VERSION from
   wikiseed/templates and writes SOURCES.json.
3. Builds the .torrent file with `torf` using the public tracker list and
   IA URLs as webseeds. Stores the file at
   {data_dir}/torrents/.torrents/{torrent_name}.torrent.
4. Inserts a torrents row + torrent_dumps rows. Uses ON CONFLICT on
   torrent_name so concurrent invocations don't double-create.
5. Uploads the .torrent file to R2 at torrents/{torrent_name}.torrent.
6. Enqueues register_torrent (seeder picks it up to start seeding) and
   publish_manifest (so the new torrent shows up in latest.json).

Idempotent: re-running on the same group is safe. Already-staged files
are detected; an existing torrent_name short-circuits the DB inserts.
"""
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from botocore.exceptions import BotoCoreError, ClientError
from torf import Torrent

from wikiseed import jobs, r2
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.paths import (
    canonical_download_path,
    torrent_file_path,
    torrent_staging_dir,
)
from wikiseed.projects import project_from_wiki
from wikiseed.trackers import PUBLIC_TRACKERS

logger = logging.getLogger("creator")

POLL_INTERVAL_SECONDS = 30

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _torrent_name(key: dict) -> str:
    if key["source_type"] == "xml_current":
        return f"wikiseed-{key['project']}-current-{key['period']}"
    if key["source_type"] == "xml_history":
        return f"wikiseed-{key['project']}-history-{key['period']}"
    return f"wikiseed-zim-{key['project']}-{key['zim_scope']}-{key['period']}"


def _resolve_dumps(key: dict) -> list:
    """Returns dump rows for the group. Raises if anything is missing or not yet IA-confirmed."""
    if key["source_type"] in ("xml_current", "xml_history"):
        with db_cursor(commit=False) as cur:
            cur.execute(
                """SELECT * FROM dumps
                   WHERE source_type = %s
                     AND period = %s
                     AND download_status = 'completed'""",
                (key["source_type"], key["period"]),
            )
            rows = [dict(r) for r in cur.fetchall()]
        rows = [r for r in rows if project_from_wiki(r["wiki_or_project"]) == key["project"]]
    else:
        with db_cursor(commit=False) as cur:
            cur.execute(
                """SELECT * FROM dumps
                   WHERE source_type = 'zim'
                     AND wiki_or_project = %s
                     AND zim_scope = %s
                     AND period = %s
                     AND download_status = 'completed'""",
                (key["project"], key["zim_scope"], key["period"]),
            )
            rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        raise RuntimeError(f"no completed dumps found for group {key}")

    missing = [r for r in rows if r["ia_confirmed_at"] is None]
    if missing:
        raise RuntimeError(
            f"group {key} not fully IA-confirmed: {len(missing)} of {len(rows)} still pending"
        )

    return rows


def _stage_files(stage: Path, dumps: list) -> None:
    """Move each dump file from its canonical location into the staging dir.

    If a file is already staged from a previous run, leave it. If it's at
    neither location something has gone wrong — fail loudly."""
    stage.mkdir(parents=True, exist_ok=True)
    for d in dumps:
        canonical = canonical_download_path(d)
        target = stage / canonical.name
        if target.exists():
            continue
        if canonical.exists():
            shutil.move(str(canonical), str(target))
        else:
            raise FileNotFoundError(
                f"dump {d['id']} file not found at canonical ({canonical}) or staged ({target})"
            )


def _write_auxiliary_files(stage: Path, key: dict, dumps: list) -> None:
    is_zim = key["source_type"] == "zim"
    readme = TEMPLATES_DIR / ("README_zim.txt" if is_zim else "README_xml.txt")
    shutil.copyfile(readme, stage / "README.txt")
    shutil.copyfile(TEMPLATES_DIR / "LICENSE.txt", stage / "LICENSE.txt")
    shutil.copyfile(TEMPLATES_DIR / "VERSION.txt", stage / "VERSION.txt")

    sources = _build_sources_json(key, dumps)
    (stage / "SOURCES.json").write_text(json.dumps(sources, indent=2, sort_keys=True))


def _build_sources_json(key: dict, dumps: list) -> dict:
    """SOURCES.json per the design doc.

    Note: torrent_info_hash is left null inside the torrent because including
    its own info hash in a file that the hash is computed from would be a
    self-referential paradox. Consumers should compute it from the .torrent
    file itself or look it up in the manifest where we record it after
    creation.
    """
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wikiseed_version": CONFIG.version,
        "torrent_name": _torrent_name(key),
        "torrent_info_hash": None,
        "files": [
            {
                "filename": Path(d["wikimedia_url"]).name,
                "size_bytes": d["filesize_bytes"],
                "sha256_wikimedia": d["sha256_wikimedia"],
                "sha256_wikiseed": d["sha256_wikiseed"],
                "wikimedia_source_url": d["wikimedia_url"],
                "ia_url": d["ia_url"],
            }
            for d in sorted(dumps, key=lambda x: x["wikimedia_url"])
        ],
    }


def _build_torrent_file(stage: Path, torrent_name: str, dumps: list) -> Torrent:
    webseeds = [d["ia_url"] for d in dumps if d["ia_url"]]
    t = Torrent(
        path=stage,
        name=torrent_name,
        trackers=[[u] for u in PUBLIC_TRACKERS],  # one tier per tracker
        webseeds=webseeds,
        created_by=f"WikiSeed/{CONFIG.version}",
        creation_date=datetime.now(timezone.utc),
        comment=f"WikiSeed preservation torrent for {torrent_name}",
        private=False,
    )
    t.generate()
    out = torrent_file_path(torrent_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    t.write(str(out), overwrite=True)
    return t


def _upload_torrent_to_r2(torrent_name: str, local_path: Path) -> Optional[str]:
    c = r2.client()
    if c is None:
        logger.warning("R2 not configured, skipping .torrent upload")
        return None
    key = f"torrents/{torrent_name}.torrent"
    try:
        c.upload_file(str(local_path), CONFIG.r2_bucket, key,
                      ExtraArgs={"ContentType": "application/x-bittorrent"})
        logger.info("uploaded .torrent to r2://%s/%s", CONFIG.r2_bucket, key)
        return key
    except (BotoCoreError, ClientError):
        logger.exception("R2 .torrent upload failed")
        return None


def _insert_torrent_row(key: dict, torrent: Torrent, dumps: list,
                        r2_key: Optional[str]) -> Optional[int]:
    """Inserts a torrent + torrent_dumps. Returns torrent_id, or None if a
    row with this name already existed (idempotent re-run)."""
    name = _torrent_name(key)
    info_hash = str(torrent.infohash)
    magnet = str(torrent.magnet())
    total = int(torrent.size)

    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO torrents (
                   torrent_name, info_hash, magnet_link, torrent_file_path,
                   torrent_file_r2_key, source_type, project, zim_scope,
                   period, total_size_bytes
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (torrent_name) DO NOTHING
               RETURNING id""",
            (
                name,
                info_hash,
                magnet,
                str(torrent_file_path(name)),
                r2_key,
                key["source_type"],
                key["project"],
                key.get("zim_scope"),
                key["period"],
                total,
            ),
        )
        row = cur.fetchone()
        if row is None:
            logger.info("torrent %s already exists, skipping inserts", name)
            return None
        torrent_id = row["id"]

        # join rows
        cur.executemany(
            "INSERT INTO torrent_dumps (torrent_id, dump_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            [(torrent_id, d["id"]) for d in dumps],
        )

    return torrent_id


def create_torrent(payload: dict) -> None:
    key = {
        "source_type": payload["source_type"],
        "project": payload["project"],
        "period": payload["period"],
    }
    if payload["source_type"] == "zim":
        key["zim_scope"] = payload["zim_scope"]

    name = _torrent_name(key)
    logger.info("creating torrent %s", name)

    dumps = _resolve_dumps(key)
    stage = torrent_staging_dir(name)
    _stage_files(stage, dumps)
    _write_auxiliary_files(stage, key, dumps)

    torrent = _build_torrent_file(stage, name, dumps)
    logger.info("built %s: info_hash=%s, %d files, %d bytes",
                name, torrent.infohash, len(dumps), int(torrent.size))

    local_torrent = torrent_file_path(name)
    r2_key = _upload_torrent_to_r2(name, local_torrent)

    torrent_id = _insert_torrent_row(key, torrent, dumps, r2_key)
    if torrent_id is None:
        return  # duplicate

    jobs.enqueue("register_torrent", {"torrent_id": torrent_id})
    jobs.enqueue("publish_manifest")
    logger.info("torrent %s ready (id=%d)", name, torrent_id)


def main() -> None:
    setup("creator")
    logger.info("creator started")
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
            jobs.fail(job["id"], str(e))


if __name__ == "__main__":
    main()
