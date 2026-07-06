"""Standard logging setup shared by the Glue entrypoint, CLI, and tests."""
import logging
import sys

from etl_platform.config import PIPELINE


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, PIPELINE.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
