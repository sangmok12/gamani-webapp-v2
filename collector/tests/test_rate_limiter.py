import pytest

from gamani_collector.rate_limiter import RateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)
        self.now += seconds


def test_first_request_does_not_wait() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(
        requests_per_second=1.0,
        clock=fake_time.monotonic,
        sleep=fake_time.sleep,
    )

    limiter.wait()

    assert fake_time.delays == []


def test_second_immediate_request_waits_for_remaining_interval() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(
        requests_per_second=1.0,
        clock=fake_time.monotonic,
        sleep=fake_time.sleep,
    )

    limiter.wait()
    fake_time.now = 0.25
    limiter.wait()

    assert fake_time.delays == [0.75]


def test_request_after_interval_does_not_wait() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(
        requests_per_second=1.0,
        clock=fake_time.monotonic,
        sleep=fake_time.sleep,
    )

    limiter.wait()
    fake_time.now = 1.5
    limiter.wait()

    assert fake_time.delays == []


@pytest.mark.parametrize("requests_per_second", [0, -1])
def test_invalid_rate_is_rejected(requests_per_second: float) -> None:
    with pytest.raises(ValueError, match="must be greater than 0"):
        RateLimiter(requests_per_second)
