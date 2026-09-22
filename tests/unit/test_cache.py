"""Tests for shopify/cache.py (I12)."""

import pytest

from bigbrain.shopify.cache import TTLCache


def test_set_then_get_returns_same_value():
    """Test 1: set() then get() returns the same value."""
    cache = TTLCache(ttl_s=10)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_get_missing_key_returns_none():
    """Test 2: get() on a missing key returns None."""
    cache = TTLCache(ttl_s=10)
    assert cache.get("missing") is None


def test_expired_entry_evicted_on_read():
    """Test 3: expired entry is evicted on read (not just masked)."""
    # Create a fake clock: a mutable value we can advance
    clock = [0.0]

    def fake_now():
        return clock[0]

    cache = TTLCache(ttl_s=10, now_fn=fake_now)

    # Set at t=0 with ttl_s=10
    cache.set("key1", "value1")
    assert len(cache) == 1

    # Advance fake clock to t=10 (exactly at expiry boundary)
    clock[0] = 10.0

    # get() should return None and evict the entry
    assert cache.get("key1") is None
    assert len(cache) == 0  # Proves eviction, not just masking


def test_just_before_expiry():
    """Test 4: just before expiry, get() still returns the value."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cache = TTLCache(ttl_s=10, now_fn=fake_now)

    # Set at t=0 with ttl_s=10
    cache.set("key1", "value1")

    # Advance to t=9.999... (just before expiry)
    clock[0] = 9.999

    # get() should still return the value
    assert cache.get("key1") == "value1"


def test_invalidate_removes_key_early():
    """Test 5: invalidate() removes a key early before TTL expiry."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cache = TTLCache(ttl_s=10, now_fn=fake_now)

    # Set a key
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    # Invalidate it early (before TTL expiry)
    cache.invalidate("key1")

    # get() should return None
    assert cache.get("key1") is None


def test_clear_empties_cache():
    """Test 6: clear() empties the cache."""
    clock = [0.0]

    def fake_now():
        return clock[0]

    cache = TTLCache(ttl_s=10, now_fn=fake_now)

    # Set multiple entries
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")
    assert len(cache) == 3

    # Clear the cache
    cache.clear()

    # Should be empty
    assert len(cache) == 0


def test_ttl_zero_raises():
    """Test 7: TTLCache(ttl_s=0) raises ValueError."""
    with pytest.raises(ValueError, match="ttl_s must be > 0"):
        TTLCache(ttl_s=0)


def test_ttl_negative_raises():
    """Test 7: TTLCache(ttl_s=-1) raises ValueError."""
    with pytest.raises(ValueError, match="ttl_s must be > 0"):
        TTLCache(ttl_s=-1)
