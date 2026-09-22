"""Per-store token-bucket rate limiting (I12). Shopify publishes no specific rate-limit
numbers for anonymous/keyless access (docs/SHOPIFY_NOTES.md), so this defaults to a
conservative, configurable rate rather than a documented ceiling. `acquire()` waits
until a token is available rather than raising -- patience over guessing a hard cutoff.
"""

import asyncio
import time


class TokenBucket:
    """Refills at `rate` tokens/second up to `capacity` (default: `capacity == rate`,
    i.e. no burst beyond one second's worth of tokens). Async-safe: concurrent callers
    serialize through an internal lock so the bucket's real rate is respected exactly,
    which is the point for a per-store outbound rate limit.
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    async def acquire(self, cost: float = 1.0) -> None:
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= cost:
                    self._tokens -= cost
                    return
                deficit = cost - self._tokens
                wait_s = deficit / self.rate
                await asyncio.sleep(wait_s)
