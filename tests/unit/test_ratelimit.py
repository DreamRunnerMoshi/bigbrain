"""Tests for shopify/ratelimit.py (I12)."""

import time

import pytest

from bigbrain.shopify.ratelimit import TokenBucket


@pytest.mark.asyncio
async def test_acquire_immediate_when_tokens_available():
    """Test 1: acquire() returns immediately when tokens are available."""
    bucket = TokenBucket(rate=1000)
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # With high rate (1000/s), should be nearly instant (no meaningful delay)
    assert elapsed < 0.01


@pytest.mark.asyncio
async def test_rate_is_respected():
    """Test 2: rate is respected with high precision."""
    bucket = TokenBucket(rate=100, capacity=1)
    start = time.monotonic()
    # Call acquire 3 times in a row
    # First acquire uses the 1 initial token (no wait)
    # Second and third must wait for refill
    await bucket.acquire()
    await bucket.acquire()
    await bucket.acquire()
    elapsed = time.monotonic() - start

    # 2 of 3 acquisitions must wait for a refill
    # Each refill takes 1/100 = 0.01 seconds
    # So minimum time should be ~0.02 seconds
    # Use generous tolerance (0.015) to avoid flakiness
    assert elapsed >= 0.015


def test_rate_zero_raises():
    """Test 3: TokenBucket(rate=0) raises ValueError."""
    with pytest.raises(ValueError, match="rate must be > 0"):
        TokenBucket(rate=0)


def test_rate_negative_raises():
    """Test 3: TokenBucket(rate=-1) raises ValueError."""
    with pytest.raises(ValueError, match="rate must be > 0"):
        TokenBucket(rate=-1)


def test_tokens_never_exceed_capacity():
    """Test 4: tokens never exceed capacity after a long idle period."""
    bucket = TokenBucket(rate=100, capacity=10)
    # Manually push _last far into the past
    bucket._last -= 1000
    # Call _refill directly
    bucket._refill()
    # Tokens should be clamped to capacity
    assert bucket._tokens == bucket.capacity
