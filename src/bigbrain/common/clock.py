"""Clock abstraction: real UTC time by default, injectable for deterministic tests.
Needed wherever code reads 'now' for envelope `sent_at`, TTL/freshness-window checks
(I9, I10, I12), or `valid_until`/`deadline` fields -- see BIGBRAIN_SPEC.md section 6.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real wall-clock time, always UTC-aware."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests: starts at `start` (default 2026-01-01T00:00:00Z),
    only moves when `advance()` is called.
    """

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


def rfc3339(dt: datetime) -> str:
    """RFC3339 string for wire messages (envelope `sent_at`, payload `deadline`/`valid_until`)."""
    return dt.astimezone(UTC).isoformat()
