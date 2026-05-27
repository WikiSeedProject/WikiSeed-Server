"""Publisher — builds and publishes the manifest and status JSON.

Listens for: publish_manifest, publish_status

Stub. When implementing:

publish_manifest:
- Build manifest dict from torrents + dumps + torrent_dumps (see design doc
  Manifest section for exact shape).
- Write to CONFIG.manifest_dir/latest.json (atomic: write to tmp then rename).
- Upload to R2:
    s3://{R2_BUCKET}/manifest/latest.json
    s3://{R2_BUCKET}/manifest/versions/{YYYY-MM-DD-HH}.json
  Then list versions/, delete all but the newest 12.
- Push to GitHub fallback: commit manifest/latest.json to the
  CONFIG.github_manifest_branch branch of CONFIG.github_repo. Use a single-file
  commit via the GitHub contents API (PUT /repos/{owner}/{repo}/contents/{path}).
- Use boto3 with endpoint_url='https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com'
  for R2.

publish_status:
- Build public.json and ops.json (see design doc Status JSON section).
- Upload to:
    s3://{R2_BUCKET}/status/public.json
    s3://{R2_BUCKET}/status/ops.json
- Status pushes are hourly and do not need versioning.
"""
import logging
import time

from wikiseed import jobs
from wikiseed.logging_setup import setup

logger = logging.getLogger("publisher")

POLL_INTERVAL_SECONDS = 30


def publish_manifest(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("publisher.publish_manifest is not yet implemented")


def publish_status(payload: dict) -> None:
    # TODO: implement per docstring above.
    raise NotImplementedError("publisher.publish_status is not yet implemented")


HANDLERS = {
    "publish_manifest": publish_manifest,
    "publish_status": publish_status,
}


def main() -> None:
    setup("publisher")
    logger.info("publisher started (stub)")
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
