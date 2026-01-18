"""Logging configuration for WikiSeed."""

import logging
import os
import sys


def setup_logging(name: str | None = None, level: str | None = None) -> logging.Logger:
    """Configure logging for WikiSeed components.

    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to LOG_LEVEL env var or INFO

    Returns:
        Configured logger
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    # Configure root logger if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )

    # Return logger for specific component
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, level.upper()))

    return logger
