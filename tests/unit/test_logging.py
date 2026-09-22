"""Unit tests for bigbrain.common.logging."""

import logging
import sys

from bigbrain.common.logging import get_logger, setup_logging


def test_get_logger_names_spaces_under_bigbrain() -> None:
    assert get_logger("x").name == "bigbrain.x"


def test_setup_logging_attaches_one_stderr_handler() -> None:
    setup_logging()
    logger = logging.getLogger("bigbrain")

    assert len(logger.handlers) == 1
    assert logger.handlers[0].stream is sys.stderr


def test_setup_logging_does_not_duplicate_handlers() -> None:
    setup_logging()
    logger = logging.getLogger("bigbrain")
    handlers_after_first = list(logger.handlers)

    setup_logging()

    assert logger.handlers == handlers_after_first


def test_setup_logging_sets_level_case_insensitively() -> None:
    setup_logging("warning")

    assert logging.getLogger("bigbrain").level == logging.WARNING
