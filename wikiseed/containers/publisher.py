"""Publisher — builds and publishes the manifest and status JSON.

Listens for:
    publish_manifest  - regenerate manifest, write local copy, push to R2 + GitHub
    publish_status    - regenerate public.json + ops.json, push to R2

The local copy on the SSD (CONFIG.manifest_dir/latest.json) is the durable
source-of-truth backup and is always written first. R2 and GitHub
publication failures are logged but do not fail the job — the local file
is still the truth.

R2 layout:
    manifest/latest.json
    manifest/versions/{YYYY-MM-DD-HH}.json   (12 retained, oldest pruned)
    status/public.json
    status/ops.json

GitHub fallback: a single PUT against the contents API on the configured
manifest branch.
"""
import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import boto3
import requests
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from wikiseed import jobs
from wikiseed.config import CONFIG
from wikiseed.db import cursor as db_cursor
from wikiseed.logging_setup import setup
from wikiseed.projects import project_from_wiki

logger = logging.getLogger("publisher")

POLL_INTERVAL_SECONDS = 30
MANIFEST_VERSIONS_RETAINED = 12


def _r2_client():
    if not (CONFIG.r2_account_id and CONFIG.r2_access_key_id and CONFIG.r2_secret_access_key):
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{CONFIG.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=CONFIG.r2_access_key_id,
        aws_secret_access_key=CONFIG.r2_secret_access_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----- manifest -----

def build_manifest() -> dict:
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT id, torrent_name, info_hash, magnet_link, torrent_file_r2_key,
                      source_type, project, zim_scope, period, created_at,
                      total_size_bytes, seeder_count, health_status
               FROM torrents
               ORDER BY created_at DESC"""
        )
        torrents = [dict(r) for r in cur.fetchall()]

    torrent_ids = [t["id"] for t in torrents]
    files_by_torrent: dict = {tid: [] for tid in torrent_ids}
    if torrent_ids:
        with db_cursor(commit=False) as cur:
            cur.execute(
                """SELECT td.torrent_id,
                          d.wikimedia_url, d.wiki_or_project, d.language,
                          d.source_type, d.zim_scope, d.zim_topic,
                          d.filesize_bytes, d.sha256_wikiseed, d.ia_url
                   FROM torrent_dumps td
                   JOIN dumps d ON d.id = td.dump_id
                   WHERE td.torrent_id = ANY(%s)
                   ORDER BY d.wikimedia_url ASC""",
                (torrent_ids,),
            )
            for row in cur.fetchall():
                files_by_torrent[row["torrent_id"]].append(dict(row))

    return {
        "generated_at": _now_iso(),
        "version": CONFIG.version,
        "torrents": [_torrent_to_manifest(t, files_by_torrent[t["id"]]) for t in torrents],
    }


def _display_name(t: dict) -> str:
    project = t["project"].capitalize()
    if t["source_type"] == "xml_current":
        return f"WikiSeed — {project} Current Exports — {t['period']}"
    if t["source_type"] == "xml_history":
        return f"WikiSeed — {project} History Exports — {t['period']}"
    scope = (t["zim_scope"] or "").capitalize()
    return f"WikiSeed — {project} ZIM {scope} — {t['period']}"


def _torrent_to_manifest(t: dict, files: list) -> dict:
    torrent_url = None
    if t["torrent_file_r2_key"]:
        base = CONFIG.torrent_cdn_base.rstrip("/")
        torrent_url = f"{base}/{Path(t['torrent_file_r2_key']).name}"
    out = {
        "id": t["torrent_name"],
        "name": _display_name(t),
        "source_type": t["source_type"],
        "project": t["project"],
        "period": t["period"],
        "magnet": t["magnet_link"],
        "torrent_url": torrent_url,
        "total_size_bytes": t["total_size_bytes"],
        "seeder_count": t["seeder_count"],
        "health_status": t["health_status"],
        "created_at": _iso(t["created_at"]),
        "files": [_file_to_manifest(f) for f in files],
    }
    if t["zim_scope"]:
        out["zim_scope"] = t["zim_scope"]
    return out


def _file_to_manifest(f: dict) -> dict:
    is_zim = f["source_type"] == "zim"
    project = f["wiki_or_project"] if is_zim else project_from_wiki(f["wiki_or_project"])
    out = {
        "filename": Path(f["wikimedia_url"]).name,
        "wiki": None if is_zim else f["wiki_or_project"],
        "language": f["language"],
        "project": project,
        "size_bytes": f["filesize_bytes"],
        "sha256_wikiseed": f["sha256_wikiseed"],
        "ia_url": f["ia_url"],
        "wikimedia_source_url": f["wikimedia_url"],
    }
    if is_zim:
        out["zim_scope"] = f["zim_scope"]
        out["zim_topic"] = f["zim_topic"]
    return out


def write_local_manifest(manifest: dict) -> Path:
    CONFIG.manifest_dir.mkdir(parents=True, exist_ok=True)
    target = CONFIG.manifest_dir / "latest.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    # rename is atomic on POSIX; readers never see a half-written file.
    os.replace(tmp, target)
    return target


def upload_manifest_to_r2(manifest: dict) -> None:
    c = _r2_client()
    if c is None:
        logger.warning("R2 not configured, skipping manifest upload")
        return
    payload = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    version_key = f"manifest/versions/{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}.json"
    try:
        c.put_object(Bucket=CONFIG.r2_bucket, Key="manifest/latest.json",
                     Body=payload, ContentType="application/json")
        c.put_object(Bucket=CONFIG.r2_bucket, Key=version_key,
                     Body=payload, ContentType="application/json")
        _prune_old_manifest_versions(c)
        logger.info("uploaded manifest to R2 (latest + %s)", version_key)
    except (BotoCoreError, ClientError):
        logger.exception("R2 manifest upload failed")


def _prune_old_manifest_versions(c) -> None:
    resp = c.list_objects_v2(Bucket=CONFIG.r2_bucket, Prefix="manifest/versions/")
    contents = resp.get("Contents", [])
    if len(contents) <= MANIFEST_VERSIONS_RETAINED:
        return
    keys = sorted([o["Key"] for o in contents])  # YYYY-MM-DD-HH sorts chronologically
    to_delete = keys[: len(keys) - MANIFEST_VERSIONS_RETAINED]
    c.delete_objects(
        Bucket=CONFIG.r2_bucket,
        Delete={"Objects": [{"Key": k} for k in to_delete]},
    )
    logger.info("pruned %d old manifest versions", len(to_delete))


def push_manifest_to_github(manifest: dict) -> None:
    if not (CONFIG.github_token and CONFIG.github_repo):
        logger.warning("GitHub not configured, skipping manifest push")
        return
    path = "manifest/latest.json"
    url = f"https://api.github.com/repos/{CONFIG.github_repo}/contents/{path}"
    headers = {
        "Authorization": f"token {CONFIG.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    branch = CONFIG.github_manifest_branch
    payload = json.dumps(manifest, indent=2, sort_keys=True)

    try:
        # The contents API requires the prior sha when updating an existing file.
        get_r = requests.get(f"{url}?ref={branch}", headers=headers, timeout=30)
        sha = get_r.json().get("sha") if get_r.status_code == 200 else None

        body = {
            "message": f"Update manifest {manifest['generated_at']}",
            "content": base64.b64encode(payload.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        put_r = requests.put(url, headers=headers, json=body, timeout=60)
        put_r.raise_for_status()
        logger.info("pushed manifest to github://%s/%s on branch %s",
                    CONFIG.github_repo, path, branch)
    except requests.RequestException:
        logger.exception("GitHub manifest push failed")


def publish_manifest(payload: dict) -> None:
    manifest = build_manifest()
    local = write_local_manifest(manifest)
    logger.info("manifest written locally: %s (%d torrents)",
                local, len(manifest["torrents"]))
    upload_manifest_to_r2(manifest)
    push_manifest_to_github(manifest)


# ----- status -----

def build_public_status() -> dict:
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE health_status = 'healthy') AS healthy,
                      COUNT(*) FILTER (WHERE health_status = 'warning') AS warning,
                      COALESCE(SUM(total_size_bytes), 0) AS total_size
               FROM torrents"""
        )
        totals = dict(cur.fetchone())
        cur.execute(
            """SELECT project,
                      COUNT(*) AS torrents,
                      COUNT(*) FILTER (WHERE health_status = 'healthy') AS healthy
               FROM torrents
               GROUP BY project
               ORDER BY project"""
        )
        by_project = {r["project"]: {"torrents": r["torrents"], "healthy": r["healthy"]}
                      for r in cur.fetchall()}
        cur.execute(
            """SELECT torrent_name, project, period, source_type, created_at
               FROM torrents
               ORDER BY created_at DESC
               LIMIT 10"""
        )
        recent = [{
            "id": r["torrent_name"],
            "project": r["project"],
            "period": r["period"],
            "source_type": r["source_type"],
            "created_at": _iso(r["created_at"]),
        } for r in cur.fetchall()]

    return {
        "updated_at": _now_iso(),
        "collection": {
            "total_torrents": totals["total"],
            "healthy_torrents": totals["healthy"],
            "warning_torrents": totals["warning"],
            "total_size_bytes": int(totals["total_size"]),
        },
        "by_project": by_project,
        "recent_additions": recent,
    }


def _infer_phase(progress: dict) -> str:
    for p in progress.values():
        if p["completed"] < p["total"]:
            return "downloading"
    return "idle"


def build_ops_status() -> dict:
    empty = {"total": 0, "completed": 0, "failed": 0}
    with db_cursor(commit=False) as cur:
        cur.execute(
            """SELECT COALESCE(SUM(filesize_bytes), 0) AS bytes
               FROM dumps
               WHERE download_status = 'completed'"""
        )
        used_bytes = int(cur.fetchone()["bytes"])

        cur.execute(
            """SELECT COALESCE(SUM(total_size_bytes), 0) AS bytes
               FROM torrents
               WHERE eligible_for_deletion = TRUE AND local_files_deleted_at IS NULL"""
        )
        eligible_bytes = int(cur.fetchone()["bytes"])

        cur.execute(
            """SELECT source_type,
                      COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE download_status = 'completed') AS completed,
                      COUNT(*) FILTER (WHERE download_status = 'failed') AS failed
               FROM dumps
               WHERE period = to_char(NOW(), 'YYYY-MM')
               GROUP BY source_type"""
        )
        progress = {r["source_type"]: {"total": r["total"], "completed": r["completed"], "failed": r["failed"]}
                    for r in cur.fetchall()}

        cur.execute(
            "SELECT COUNT(*) AS active FROM torrents WHERE health_status = 'recovering'"
        )
        recovering = cur.fetchone()["active"]

        cur.execute(
            """SELECT torrent_id, event_type, seeder_count, timestamp, notes
               FROM health_events
               ORDER BY timestamp DESC
               LIMIT 50"""
        )
        recent_events = [{
            "torrent_id": r["torrent_id"],
            "event_type": r["event_type"],
            "seeder_count": r["seeder_count"],
            "timestamp": _iso(r["timestamp"]),
            "notes": r["notes"],
        } for r in cur.fetchall()]

        cur.execute(
            """SELECT torrent_name, project, period, total_size_bytes
               FROM torrents
               WHERE eligible_for_deletion = TRUE AND local_files_deleted_at IS NULL
               ORDER BY created_at ASC
               LIMIT 20"""
        )
        deletion_queue = [{
            "id": r["torrent_name"],
            "project": r["project"],
            "period": r["period"],
            "size_bytes": r["total_size_bytes"],
        } for r in cur.fetchall()]

    return {
        "updated_at": _now_iso(),
        "storage": {
            "budget_bytes": CONFIG.storage_budget_bytes,
            "used_bytes": used_bytes,
            "eligible_for_deletion_bytes": eligible_bytes,
        },
        "pipeline": {
            "current_phase": _infer_phase(progress),
            "xml_current_progress": progress.get("xml_current", empty.copy()),
            "xml_history_progress": progress.get("xml_history", empty.copy()),
            "zim_progress": progress.get("zim", empty.copy()),
        },
        "redownloads": {"active": recovering, "recent": []},
        "deletion_queue": deletion_queue,
        "recent_events": recent_events,
    }


def publish_status(payload: dict) -> None:
    public = build_public_status()
    ops = build_ops_status()
    c = _r2_client()
    if c is None:
        logger.warning("R2 not configured, skipping status upload")
        return
    try:
        for key, doc in (("status/public.json", public), ("status/ops.json", ops)):
            c.put_object(
                Bucket=CONFIG.r2_bucket, Key=key,
                Body=json.dumps(doc, indent=2, sort_keys=True).encode("utf-8"),
                ContentType="application/json",
            )
        logger.info("published status JSON to R2 (public + ops)")
    except (BotoCoreError, ClientError):
        logger.exception("R2 status upload failed")


# ----- entrypoint -----

HANDLERS = {
    "publish_manifest": publish_manifest,
    "publish_status": publish_status,
}


def main() -> None:
    setup("publisher")
    logger.info("publisher started")
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
            jobs.fail(job["id"], str(e), retry=False)


if __name__ == "__main__":
    main()
