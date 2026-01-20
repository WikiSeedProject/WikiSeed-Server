"""Wikimedia API client for querying dump status."""

import time
from typing import Any, Dict, Optional

import requests

from src.common.logging import setup_logging

logger = setup_logging(__name__)


class WikimediaClient:
    """Client for interacting with Wikimedia dump API."""

    BASE_URL = "https://dumps.wikimedia.org"
    USER_AGENT = "WikiSeed/0.1.0 (https://wikiseed.app; hello@wikiseed.app)"
    REQUEST_TIMEOUT = 30

    def __init__(self, max_retries: int = 3) -> None:
        """Initialize Wikimedia API client.

        Args:
            max_retries: Maximum number of retries for failed requests
        """
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def get_dump_status(self, wiki: str, cycle_date: str) -> Optional[Dict[str, Any]]:
        """Get dump status for a specific wiki and cycle date.

        Args:
            wiki: Wiki database name (e.g., 'enwiki')
            cycle_date: Cycle date in YYYY-MM-DD format (e.g., '2026-01-20')

        Returns:
            Dump status dictionary or None if not found
        """
        # Convert YYYY-MM-DD to YYYYMMDD format for Wikimedia API
        cycle_date_compact = cycle_date.replace("-", "")

        # Try dumpstatus.json first (current/latest dumps)
        url = f"{self.BASE_URL}/{wiki}/{cycle_date_compact}/dumpstatus.json"

        try:
            response = self._get_with_retry(url)
            if response and response.status_code == 200:
                data = response.json()
                logger.debug(f"Found dump status for {wiki} on {cycle_date}")
                return data

            # If 404, the dump might not exist for this date
            if response and response.status_code == 404:
                logger.debug(f"No dump found for {wiki} on {cycle_date}")
                return None

        except Exception as e:
            logger.error(f"Error fetching dump status for {wiki} on {cycle_date}: {e}")
            return None

        return None

    def get_available_wikis(self) -> list[str]:
        """Get list of all available wikis.

        Returns:
            List of wiki database names

        Note:
            This is a simplified version. In production, you might want to
            scrape the dumps.wikimedia.org index page or use the Wikimedia API.
        """
        # For now, return a hardcoded list of major wikis
        # TODO: Implement dynamic wiki discovery
        return [
            # Major Wikipedias
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
            "nlwiki",
            "arwiki",
            "hewiki",
            "fawiki",
            "idwiki",
            "kowiki",
            "viwiki",
            "trwiki",
            "svwiki",
            "ukwiki",
            # Major Wiktionaries
            "enwiktionary",
            "frwiktionary",
            "dewiktionary",
            "ruwiktionary",
            # Other projects
            "enwikiquote",
            "enwikibooks",
            "enwikinews",
            "enwikisource",
            "enwikiversity",
            "enwikivoyage",
        ]

    def _get_with_retry(self, url: str) -> Optional[requests.Response]:
        """Make GET request with exponential backoff retry.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if all retries failed
        """
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)

                # Return response even if not successful (caller will handle)
                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff: 1s, 2s, 4s
                continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                continue

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
