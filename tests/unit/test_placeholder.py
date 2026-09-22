"""Scaffold checks.

Placeholder for M1 (wire format & crypto); see docs/PROGRESS.md. Delete or replace this
file as soon as the first real module lands.
"""

import importlib

import bigbrain

# Module responsibilities live in CLAUDE.md and spec section 5; the scaffold only asserts
# that the src-layout packages import under `uv run pytest`.
SUBPACKAGES = (
    "broker",
    "buyer",
    "common",
    "directory",
    "llm",
    "mailbox",
    "merchant",
    "payments",
    "profiler",
    "protocol",
    "shopify",
    "taxonomy",
    "transport",
    "ui",
)


def test_package_imports() -> None:
    """`bigbrain` and every declared subpackage are importable."""
    assert bigbrain.__version__ == "0.1.0"
    for name in SUBPACKAGES:
        module = importlib.import_module(f"bigbrain.{name}")
        assert module.__doc__
