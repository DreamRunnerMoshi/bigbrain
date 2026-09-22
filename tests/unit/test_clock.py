"""Tests for bigbrain.common.clock module."""

from datetime import UTC, datetime, timedelta

from bigbrain.common.clock import FixedClock, SystemClock, rfc3339


class TestSystemClock:
    """Test SystemClock class."""

    def test_now_returns_timezone_aware_datetime(self) -> None:
        """SystemClock().now() returns a timezone-aware datetime."""
        clock = SystemClock()
        now = clock.now()

        assert isinstance(now, datetime)
        assert now.tzinfo is not None


class TestFixedClock:
    """Test FixedClock class."""

    def test_returns_same_value_until_advance(self) -> None:
        """FixedClock returns same value on repeated .now() calls until .advance()."""
        clock = FixedClock()

        # Multiple calls should return the same value
        now1 = clock.now()
        now2 = clock.now()
        now3 = clock.now()

        assert now1 == now2 == now3

    def test_advance_moves_time(self) -> None:
        """FixedClock reflects time changes after .advance() is called."""
        clock = FixedClock()

        initial = clock.now()
        delta = timedelta(hours=1)
        clock.advance(delta)

        after = clock.now()
        assert after == initial + delta

    def test_custom_start_time(self) -> None:
        """FixedClock can start at a custom time."""
        custom_start = datetime(2025, 6, 15, 12, 30, 0, tzinfo=UTC)
        clock = FixedClock(start=custom_start)

        assert clock.now() == custom_start


class TestRfc3339:
    """Test rfc3339 function."""

    def test_known_datetime_produces_expected_iso8601(self) -> None:
        """rfc3339() on a known fixed datetime produces expected ISO-8601 string."""
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = rfc3339(dt)

        # Should contain the date and time
        assert "2026-01-01T12:00:00" in result

        # Should end with UTC offset
        assert result.endswith("+00:00")
