"""Scraper worker - polls for discover_wikis jobs and processes them."""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.common.config import load_config
from src.common.database import get_db_connection
from src.common.logging import setup_logging
from src.scraper.wikimedia import WikimediaClient

logger = setup_logging(__name__)


class ScraperWorker:
    """Worker that discovers Wikimedia dumps and creates download jobs."""

    def __init__(self, poll_interval: int = 30) -> None:
        """Initialize scraper worker.

        Args:
            poll_interval: Seconds between job queue polls (default: 30)
        """
        self.poll_interval = poll_interval
        self.running = False
        self.config = load_config()
        self.wikimedia_client = WikimediaClient()

        logger.info(f"Scraper worker initialized (poll interval: {poll_interval}s)")

    def run(self) -> None:
        """Run the worker loop."""
        self.running = True
        logger.info("Scraper worker started")

        while self.running:
            try:
                self._process_pending_jobs()
            except Exception as e:
                logger.error(f"Error processing jobs: {e}", exc_info=True)

            # Sleep between polling cycles
            time.sleep(self.poll_interval)

    def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        logger.info("Shutting down scraper worker")
        self.running = False

    def _process_pending_jobs(self) -> None:
        """Poll database for pending discover_wikis jobs and process them."""
        conn = get_db_connection()

        try:
            # Get pending discover_wikis jobs
            cursor = conn.execute(
                """
                SELECT id, cycle_date, params
                FROM jobs
                WHERE job_type = 'discover_wikis'
                  AND status = 'pending'
                  AND (next_retry_at IS NULL OR next_retry_at <= CURRENT_TIMESTAMP)
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            job = cursor.fetchone()

            if not job:
                return

            job_id = job["id"]
            cycle_date = job["cycle_date"]
            params = json.loads(job["params"]) if job["params"] else {}

            logger.info(f"Processing discover_wikis job {job_id} for cycle {cycle_date}")

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

            # Process the job
            try:
                self._discover_dumps(job_id, cycle_date, params)

                # Mark job as complete
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP,
                        result = ?
                    WHERE id = ?
                    """,
                    (json.dumps({"success": True}), job_id),
                )
                conn.commit()
                logger.info(f"Job {job_id} completed successfully")

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

    def _discover_dumps(self, job_id: int, cycle_date: str, params: Dict[str, Any]) -> None:
        """Discover dumps for a given cycle date.

        Args:
            job_id: Job ID being processed
            cycle_date: Cycle date (YYYY-MM-DD format)
            params: Job parameters (may contain wiki filter, test mode, etc.)
        """
        # Get list of wikis to process (from params or default list)
        wikis = params.get("wikis", self._get_default_wikis())
        test_mode = params.get("test_mode", False)

        if test_mode:
            # In test mode, only process a few small wikis
            wikis = wikis[:5]
            logger.info(f"Test mode: processing only {len(wikis)} wikis")

        logger.info(f"Discovering dumps for {len(wikis)} wikis on cycle {cycle_date}")

        dumps_discovered = 0
        jobs_created = 0
        conn = get_db_connection()

        try:
            for wiki in wikis:
                try:
                    # Get dump status from Wikimedia
                    dump_info = self.wikimedia_client.get_dump_status(wiki, cycle_date)

                    if not dump_info or not dump_info.get("jobs"):
                        logger.debug(f"No dumps found for {wiki} on {cycle_date}")
                        continue

                    # Note: archive.today archiving removed due to rate limiting
                    # Manual archiving can be done separately if needed
                    archive_url = None

                    # Process each dump file
                    for job_name, job_data in dump_info["jobs"].items():
                        if job_data.get("status") != "done":
                            continue

                        files = job_data.get("files", {})
                        for filename, file_data in files.items():
                            dumps_discovered += 1

                            # Store dump in database
                            dump_id = self._store_dump(
                                conn=conn,
                                wiki=wiki,
                                cycle_date=cycle_date,
                                job_name=job_name,
                                filename=filename,
                                file_data=file_data,
                                archive_url=archive_url,
                            )

                            # Create download job for this dump
                            if dump_id:
                                self._create_download_job(
                                    conn=conn,
                                    parent_job_id=job_id,
                                    dump_id=dump_id,
                                    cycle_date=cycle_date,
                                )
                                jobs_created += 1

                    logger.info(f"Processed {wiki}: {dumps_discovered} dumps discovered")

                except Exception as e:
                    logger.error(f"Error processing wiki {wiki}: {e}", exc_info=True)
                    continue

                # Rate limiting - be respectful to Wikimedia servers
                time.sleep(0.6)  # ~100 requests per minute max

            logger.info(
                f"Discovery complete: {dumps_discovered} dumps discovered, {jobs_created} download jobs created"
            )

        finally:
            conn.close()

    def _store_dump(
        self,
        conn: Any,
        wiki: str,
        cycle_date: str,
        job_name: str,
        filename: str,
        file_data: Dict[str, Any],
        archive_url: Optional[str],
    ) -> Optional[int]:
        """Store dump metadata in database.

        Returns:
            Dump ID if stored successfully, None otherwise
        """
        try:
            # Parse wiki database name to extract project and language
            # Format: enwiki, frwiktionary, etc.
            project, language = self._parse_wiki_name(wiki)

            # Build Wikimedia URL
            # Wikimedia returns relative URLs (e.g., "/enwiki/20260101/filename"), prepend base URL
            relative_url = file_data.get("url", f"/{wiki}/{cycle_date.replace('-', '')}/{filename}")
            wikimedia_url = f"https://dumps.wikimedia.org{relative_url}"

            cursor = conn.execute(
                """
                INSERT INTO dumps (
                    project, language, wiki_db_name, cycle_date, dump_type, filename,
                    is_history, size_bytes, md5, sha1, wikimedia_url, archive_today_url,
                    wikimedia_status, our_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wiki_db_name, cycle_date, filename) DO UPDATE SET
                    size_bytes = excluded.size_bytes,
                    md5 = excluded.md5,
                    sha1 = excluded.sha1,
                    wikimedia_url = excluded.wikimedia_url,
                    wikimedia_status = excluded.wikimedia_status
                """,
                (
                    project,
                    language,
                    wiki,
                    cycle_date,
                    job_name,
                    filename,
                    1 if "history" in job_name else 0,
                    file_data.get("size"),
                    file_data.get("md5"),
                    file_data.get("sha1"),
                    wikimedia_url,
                    archive_url,
                    "done",
                    "pending",
                ),
            )
            conn.commit()

            # Get the dump ID
            cursor = conn.execute(
                "SELECT id FROM dumps WHERE wiki_db_name = ? AND cycle_date = ? AND filename = ?",
                (wiki, cycle_date, filename),
            )
            row = cursor.fetchone()
            return row["id"] if row else None

        except Exception as e:
            logger.error(f"Error storing dump {filename}: {e}", exc_info=True)
            return None

    def _create_download_job(
        self, conn: Any, parent_job_id: int, dump_id: int, cycle_date: str
    ) -> None:
        """Create a download_dump job for the given dump."""
        try:
            conn.execute(
                """
                INSERT INTO jobs (job_type, status, parent_job_id, dump_id, cycle_date, params)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "download_dump",
                    "pending",
                    parent_job_id,
                    dump_id,
                    cycle_date,
                    json.dumps({}),
                ),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error creating download job for dump {dump_id}: {e}", exc_info=True)

    def _parse_wiki_name(self, wiki: str) -> tuple[str, str]:
        """Parse wiki database name to extract project and language.

        Args:
            wiki: Wiki database name (e.g., 'enwiki', 'frwiktionary')

        Returns:
            Tuple of (project, language)
        """
        # Common project suffixes
        projects = [
            "wiki",
            "wiktionary",
            "wikiquote",
            "wikibooks",
            "wikinews",
            "wikisource",
            "wikiversity",
            "wikivoyage",
        ]

        for project in projects:
            if wiki.endswith(project):
                language = wiki[: -len(project)]
                return project, language

        # Default fallback
        return "wiki", wiki

    def _get_default_wikis(self) -> List[str]:
        """Get default list of wikis to scrape.

        Returns:
            List of wiki database names
        """
        # This could be loaded from config or a separate file
        # For now, return a small sample
        return [
            "enwiki",
            "frwiki",
            "dewiki",
            "eswiki",
            "jawiki",
            "zhwiki",
            "ruwiki",
            "ptwiki",
            "itwiki",
            "plwiki",
        ]
