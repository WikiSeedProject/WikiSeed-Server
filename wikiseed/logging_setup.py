import logging
import os
import sys


def setup(name: str) -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format=f"%(asctime)s {name} %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
