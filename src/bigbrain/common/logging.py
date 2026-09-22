"""Callers must never log decrypted intent/offer plaintext -- see BIGBRAIN_SPEC.md §7 and
common/audit.py for the structured, non-plaintext audit trail.
"""

import logging
import sys
from datetime import UTC, datetime


class _ISO8601Formatter(logging.Formatter):
    """Formatter stamping records with UTC ISO-8601 times (reproducibility, working rule 2)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created, tz=UTC).isoformat()


def setup_logging(level: str = "INFO") -> None:
    """Configure the "bigbrain" logger (never the root logger); safe to call repeatedly."""
    logger = logging.getLogger("bigbrain")
    logger.setLevel(level.upper())
    if logger.handlers:
        return  # already configured; never attach a second handler
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_ISO8601Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, e.g. get_logger("shopify") -> "bigbrain.shopify"."""
    return logging.getLogger(f"bigbrain.{name}")
