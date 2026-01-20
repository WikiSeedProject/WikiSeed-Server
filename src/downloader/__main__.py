"""Downloader entry point - downloads dump files from Wikimedia."""

import sys

from src.common.logging import setup_logging
from src.downloader.worker import DownloaderWorker

logger = setup_logging(__name__)


def main() -> int:
    """Run the downloader worker."""
    logger.info("Starting WikiSeed Downloader")

    worker = DownloaderWorker()

    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        worker.shutdown()
        return 0
    except Exception as e:
        logger.exception(f"Fatal error in downloader: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
