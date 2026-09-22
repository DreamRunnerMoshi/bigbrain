"""In-memory TTL cache (I12): catalog pages, product details, policy answers. `now_fn`
is injectable (default `time.monotonic`) so tests can use a fake clock instead of real
sleeps -- same pattern as common/clock.py's FixedClock.
"""

from collections.abc import Callable
from typing import Any


class TTLCache:
    def __init__(self, ttl_s: float, now_fn: Callable[[], float] | None = None) -> None:
        if ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")
        import time

        self.ttl_s = ttl_s
        self._now_fn = now_fn if now_fn is not None else time.monotonic
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._now_fn() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (self._now_fn() + self.ttl_s, value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
