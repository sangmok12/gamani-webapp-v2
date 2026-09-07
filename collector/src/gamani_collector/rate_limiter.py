import time
from collections.abc import Callable


class RateLimiter:
    """Keep requests at or below a configured rate."""

    def __init__(
        self,
        requests_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than 0")

        self._minimum_interval = 1.0 / requests_per_second
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None

    def wait(self) -> None:
        now = self._clock()

        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._minimum_interval - elapsed

            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()

        self._last_request_at = now
