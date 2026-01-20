"""Downloader worker - polls for download_dump jobs and processes them."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.common.config import load_config
from src.common.database import get_db_connection
from src.common.logging import setup_logging
from src.downloader.client import DownloadClient

logger = setup_logging(__name__)


class DownloaderWorker:
    """Worker that downloads dump files from Wikimedia."""

    def __init__(self, poll_interval: int = 30) -> None:
        """Initialize downloader worker.

        Args:
            poll_interval: Seconds between job queue polls (default: 30)
        """
        self.poll_interval = poll_interval
        self.running = False
        self.config = load_config()

        # Get download directory from config
        download_dir = self.config.get("wikiseed", {}).get("storage", {}).get("dumps_path", "/data/dumps")
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.client = DownloadClient(download_dir=self.download_dir)

        logger.info(f"Downloader worker initialized (poll interval: {poll_interval}s, download dir: {download_dir})")

    def run(self) -> None:
        """Run the worker loop."""
        self.running = True
        logger.info("Downloader worker started")

        while self.running:
            try:
                self._process_pending_jobs()
            except Exception as e:
                logger.error(f"Error processing jobs: {e}", exc_info=True)

            # Sleep between polling cycles
            time.sleep(self.poll_interval)

    def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        logger.info("Shutting down downloader worker")
        self.running = False

    def _process_pending_jobs(self) -> None:
        """Poll database for pending download_dump jobs and process them."""
        conn = get_db_connection()

        try:
            # Get pending download_dump jobs
            cursor = conn.execute(
                """
                SELECT j.id, j.dump_id, j.cycle_date, j.params,
                       d.wiki_db_name, d.filename, d.wikimedia_url, d.size_bytes, d.md5, d.sha1
                FROM jobs j
                JOIN dumps d ON j.dump_id = d.id
                WHERE j.job_type = 'download_dump'
                  AND j.status = 'pending'
                  AND (j.next_retry_at IS NULL OR j.next_retry_at <= CURRENT_TIMESTAMP)
                ORDER BY j.created_at ASC
                LIMIT 1
                """
            )
            job = cursor.fetchone()

            if not job:
                return

            job_id = job["id"]
            dump_id = job["dump_id"]
            filename = job["filename"]
            url = job["wikimedia_url"]
            expected_size = job["size_bytes"]
            expected_md5 = job["md5"]
            expected_sha1 = job["sha1"]

            logger.info(f"Processing download_dump job {job_id} for {filename}")

            # Mark job as in-progress
            conn.execute(
                """
                UPDATE jobs
                SET status = 'in_progress', started_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (job_id,),
            )
            conn.commit()

            # Process the download
            try:
                local_path = self._download_file(
                    url=url,
                    filename=filename,
                    expected_size=expected_size,
                    expected_md5=expected_md5,
                    expected_sha1=expected_sha1,
                )

                # Update dump record with local path
                conn.execute(
                    """
                    UPDATE dumps
                    SET local_path = ?,
                        downloaded_at = CURRENT_TIMESTAMP,
                        our_status = 'downloaded'
                    WHERE id = ?
                    """,
                    (str(local_path), dump_id),
                )
                conn.commit()

                # Mark job as complete
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP,
                        result = ?
                    WHERE id = ?
                    """,
                    (json.dumps({"local_path": str(local_path)}), job_id),
                )
                conn.commit()
                logger.info(f"Job {job_id} completed successfully: {local_path}")

            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}", exc_info=True)

                # Update retry count
                cursor = conn.execute("SELECT retry_count, max_retries FROM jobs WHERE id = ?", (job_id,))
                job_data = cursor.fetchone()
                retry_count = job_data["retry_count"] + 1
                max_retries = job_data["max_retries"]

                if retry_count >= max_retries:
                    # Max retries reached - mark as failed
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'failed',
                            retry_count = ?,
                            last_error = ?,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (retry_count, str(e), job_id),
                    )

                    # Mark dump as failed
                    conn.execute(
                        """
                        UPDATE dumps
                        SET our_status = 'failed',
                            error_message = ?
                        WHERE id = ?
                        """,
                        (str(e), dump_id),
                    )

                    logger.error(f"Job {job_id} failed after {retry_count} retries")
                else:
                    # Schedule retry with exponential backoff
                    retry_delays = [300, 900, 3600, 14400]  # 5m, 15m, 1h, 4h
                    delay_seconds = retry_delays[min(retry_count - 1, len(retry_delays) - 1)]

                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'pending',
                            retry_count = ?,
                            last_error = ?,
                            next_retry_at = datetime(CURRENT_TIMESTAMP, '+{} seconds')
                        WHERE id = ?
                        """.format(
                            delay_seconds
                        ),
                        (retry_count, str(e), job_id),
                    )
                    logger.warning(
                        f"Job {job_id} will retry in {delay_seconds}s (attempt {retry_count}/{max_retries})"
                    )

                conn.commit()

        finally:
            conn.close()

    def _download_file(
        self,
        url: str,
        filename: str,
        expected_size: Optional[int],
        expected_md5: Optional[str],
        expected_sha1: Optional[str],
    ) -> Path:
        """Download a file from Wikimedia.

        Args:
            url: Download URL
            filename: Filename to save as
            expected_size: Expected file size in bytes (for validation)
            expected_md5: Expected MD5 checksum (for validation)
            expected_sha1: Expected SHA1 checksum (for validation)

        Returns:
            Path to downloaded file

        Raises:
            Exception: If download or validation fails
        """
        logger.info(f"Downloading {filename} from {url}")

        # Download with resumable support
        local_path = self.client.download(
            url=url,
            filename=filename,
            expected_size=expected_size,
            expected_md5=expected_md5,
            expected_sha1=expected_sha1,
        )

        logger.info(f"Download complete: {local_path}")
        return local_path
