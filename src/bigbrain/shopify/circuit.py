"""Per-store circuit breaker (I12): "immediate stop for stores that block or restrict
access" and general resilience against a store returning errors repeatedly.
"""

from collections.abc import Callable


class CircuitOpenError(Exception):
    """Raised by `CircuitBreaker.check()` while the circuit is open."""

    def __init__(self, message: str = "circuit is open") -> None:
        super().__init__(message)


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be > 0")
        if cooldown_s <= 0:
            raise ValueError("cooldown_s must be > 0")
        import time

        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._now_fn = now_fn if now_fn is not None else time.monotonic
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._force_open = False

    @property
    def is_open(self) -> bool:
        if self._force_open:
            return True
        if self._opened_at is None:
            return False
        return self._now_fn() - self._opened_at < self.cooldown_s

    def check(self) -> None:
        """Raise CircuitOpenError if the circuit is currently open."""
        if self.is_open:
            raise CircuitOpenError()

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._opened_at = self._now_fn()

    def force_open(self) -> None:
        """Immediately open and stay open regardless of cooldown, until `reset()` --
        for a hard signal like a 403 (I12: "immediate stop for stores that block or
        restrict access")."""
        self._force_open = True

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None
        self._force_open = False
