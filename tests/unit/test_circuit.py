"""Tests for shopify/circuit.py (I12)."""

import pytest

from bigbrain.shopify.circuit import CircuitBreaker, CircuitOpenError


def test_fresh_circuit_breaker_is_closed():
    """Test 1: Fresh CircuitBreaker is closed and doesn't raise on check()."""
    cb = CircuitBreaker()
    assert cb.is_open is False
    # Should not raise
    cb.check()


def test_failures_below_threshold_circuit_stays_closed():
    """Test 2: record_failure() called fewer times than failure_threshold stays closed."""
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    assert cb.is_open is False
    cb.record_failure()
    assert cb.is_open is False


def test_failures_at_threshold_circuit_opens():
    """Test 3: record_failure() called exactly failure_threshold times opens circuit."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0, now_fn=fake_now)

    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is False

    cb.record_failure()  # Third failure
    assert cb.is_open is True

    # check() should raise
    with pytest.raises(CircuitOpenError):
        cb.check()


def test_half_open_after_cooldown():
    """Test 4: After cooldown, circuit becomes half-open (is_open returns False)."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0, now_fn=fake_now)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True

    # Advance past cooldown
    clock[0] = 61.0

    # Now should be in half-open state (is_open is False)
    assert cb.is_open is False


def test_record_success_resets_state():
    """Test 5: record_success() resets _consecutive_failures and _opened_at."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0, now_fn=fake_now)

    # Open the circuit
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()

    # Verify it's open and state is set
    assert cb.is_open is True
    assert cb._consecutive_failures == 3
    assert cb._opened_at is not None

    # Record success
    cb.record_success()

    # State should be reset
    assert cb._consecutive_failures == 0
    assert cb._opened_at is None
    assert cb.is_open is False


def test_failure_in_half_open_restarts_cooldown():
    """Test 6: Failure during half-open restarts the cooldown timer.

    This is the critical test for verifying that _opened_at is updated to the new
    failure time, not left at the original. We trace through:
    1. Open circuit at t=0
    2. Advance to t=61 (past cooldown, now half-open)
    3. Call record_failure() at t=61 (reopens)
    4. Advance to t=100 (which is only 39 seconds from the new failure, < cooldown)
    5. Verify is_open is still True (proves _opened_at was updated to 61, not 0)
    """
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0, now_fn=fake_now)

    # Step 1: Open the circuit at t=0
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open is True
    original_opened_at = cb._opened_at
    assert original_opened_at == 0.0

    # Step 2: Advance past cooldown to t=61 (half-open)
    clock[0] = 61.0
    assert cb.is_open is False  # Half-open

    # Step 3: Call record_failure() at t=61 (should reopen and update _opened_at)
    cb.record_failure()
    assert cb.is_open is True
    new_opened_at = cb._opened_at

    # Verify _opened_at was updated to the new time
    assert new_opened_at == 61.0
    assert new_opened_at != original_opened_at

    # Step 4: Advance to t=100 (39 seconds from new failure, < cooldown of 60)
    clock[0] = 100.0

    # Step 5: Verify circuit is still open (proves new _opened_at was used)
    assert cb.is_open is True


def test_force_open_stays_open():
    """Test 7: force_open() makes is_open True regardless of cooldown, even after clock advances."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(failure_threshold=3, cooldown_s=60.0, now_fn=fake_now)

    # Don't trigger natural failure-based opening
    cb.record_failure()
    assert cb.is_open is False

    # force_open() should make it open immediately
    cb.force_open()
    assert cb.is_open is True

    # Even after advancing clock arbitrarily far, should stay open
    clock[0] = 10000.0
    assert cb.is_open is True


def test_reset_after_force_open():
    """Test 8: reset() clears force_open state."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cb = CircuitBreaker(now_fn=fake_now)

    # force_open
    cb.force_open()
    assert cb.is_open is True

    # reset
    cb.reset()
    assert cb.is_open is False


def test_failure_threshold_zero_raises():
    """Test 9: CircuitBreaker(failure_threshold=0) raises ValueError."""
    with pytest.raises(ValueError, match="failure_threshold must be > 0"):
        CircuitBreaker(failure_threshold=0)


def test_failure_threshold_negative_raises():
    """Test 9: CircuitBreaker(failure_threshold=-1) raises ValueError."""
    with pytest.raises(ValueError, match="failure_threshold must be > 0"):
        CircuitBreaker(failure_threshold=-1)


def test_cooldown_zero_raises():
    """Test 9: CircuitBreaker(cooldown_s=0) raises ValueError."""
    with pytest.raises(ValueError, match="cooldown_s must be > 0"):
        CircuitBreaker(cooldown_s=0)


def test_cooldown_negative_raises():
    """Test 9: CircuitBreaker(cooldown_s=-1) raises ValueError."""
    with pytest.raises(ValueError, match="cooldown_s must be > 0"):
        CircuitBreaker(cooldown_s=-1)
