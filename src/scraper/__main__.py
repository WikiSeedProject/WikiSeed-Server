"""Scraper entry point - discovers Wikimedia dumps and archives dump pages."""

import sys
import time

from src.common.logging import setup_logging
from src.scraper.worker import ScraperWorker

logger = setup_logging(__name__)


def main() -> int:
    """Run the scraper worker."""
    logger.info("Starting WikiSeed Scraper")

    worker = ScraperWorker()

    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        worker.shutdown()
        return 0
    except Exception as e:
        logger.exception(f"Fatal error in scraper: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
