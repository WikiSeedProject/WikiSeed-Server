"""Scraper module - discovers Wikimedia dumps."""

from src.scraper.wikimedia import WikimediaClient
from src.scraper.worker import ScraperWorker

__all__ = ["ScraperWorker", "WikimediaClient"]
