"""Archive.today client for archiving Wikimedia dump pages."""

import time
from typing import Optional

import requests

from src.common.logging import setup_logging

logger = setup_logging(__name__)


class ArchiveTodayClient:
    """Client for archiving URLs to archive.today."""

    SUBMIT_URL = "https://archive.today/submit/"
    USER_AGENT = "WikiSeed/0.1.0 (https://wikiseed.app; hello@wikiseed.app)"
    REQUEST_TIMEOUT = 30

    def __init__(self, max_retries: int = 3, enabled: bool = True) -> None:
        """Initialize archive.today client.

        Args:
            max_retries: Maximum number of retries for failed requests
            enabled: Whether archiving is enabled (can be disabled for testing)
        """
        self.max_retries = max_retries
        self.enabled = enabled
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def archive_url(self, url: str) -> Optional[str]:
        """Archive a URL to archive.today.

        Args:
            url: URL to archive

        Returns:
            Archive URL if successful, None otherwise
        """
        if not self.enabled:
            logger.debug(f"Archiving disabled, skipping {url}")
            return None

        try:
            logger.info(f"Archiving {url} to archive.today")

            # Submit URL for archiving
            data = {"url": url, "anyway": "1"}

            for attempt in range(self.max_retries):
                try:
                    response = self.session.post(
                        self.SUBMIT_URL,
                        data=data,
                        timeout=self.REQUEST_TIMEOUT,
                        allow_redirects=True,
                    )

                    # archive.today redirects to the archived URL on success
                    if response.status_code == 200 and "archive." in response.url:
                        archive_url = response.url
                        logger.info(f"Archived {url} -> {archive_url}")
                        return archive_url

                    # Rate limited - wait and retry
                    if response.status_code == 429:
                        wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s
                        logger.warning(
                            f"Rate limited by archive.today, waiting {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue

                    # Other error
                    logger.warning(
                        f"Unexpected response from archive.today: {response.status_code} (attempt {attempt + 1}/{self.max_retries})"
                    )

                except requests.exceptions.Timeout:
                    logger.warning(
                        f"Timeout archiving {url} (attempt {attempt + 1}/{self.max_retries})"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(30)
                    continue

                except requests.exceptions.RequestException as e:
                    logger.error(f"Error archiving {url}: {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(30)
                    continue

            logger.error(f"Failed to archive {url} after {self.max_retries} attempts")
            return None

        except Exception as e:
            logger.error(f"Unexpected error archiving {url}: {e}", exc_info=True)
            return None

    def check_archive_exists(self, url: str) -> Optional[str]:
        """Check if an archive already exists for a URL.

        Args:
            url: URL to check

        Returns:
            Archive URL if exists, None otherwise

        Note:
            This is a simplified check. archive.today doesn't have a simple
            API for this, so we'd need to scrape the search page or use
            other methods.
        """
        # TODO: Implement archive existence check
        # For now, just return None and always create new archives
        return None
