import logging

import httpx
import pytest

from gamani_collector.http_client import EncarClient
from gamani_collector.rate_limiter import RateLimiter


def test_get_json_returns_json_object() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept"] == "application/json"
        assert request.headers["User-Agent"] == "gamani-collector/0.1.0"

        return httpx.Response(
            200,
            json={"vehicleId": "12345"},
        )

    transport = httpx.MockTransport(handle_request)

    with EncarClient(transport=transport) as client:
        result = client.get_json("/v1/readside/vehicle/12345")

    assert result == {"vehicleId": "12345"}


def test_get_json_raises_for_http_error() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handle_request)

    with EncarClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_json("/v1/missing")


def test_get_json_rejects_non_object_json() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected", "list"])

    transport = httpx.MockTransport(handle_request)

    with EncarClient(transport=transport) as client:
        with pytest.raises(ValueError, match="API response must be a JSON object"):
            client.get_json("/v1/test")


def test_get_json_retries_server_error_then_succeeds() -> None:
    request_count = 0
    delays: list[float] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return httpx.Response(500, json={"message": "temporary error"})

        return httpx.Response(200, json={"vehicleId": "12345"})

    transport = httpx.MockTransport(handle_request)

    with EncarClient(
        transport=transport,
        sleep=delays.append,
        jitter=lambda _minimum, _maximum: 0.0,
    ) as client:
        result = client.get_json("/v1/test")

    assert result == {"vehicleId": "12345"}
    assert request_count == 2
    assert delays == [1.0]


def test_get_json_does_not_retry_not_found() -> None:
    request_count = 0
    delays: list[float] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(404, json={"message": "Not Found"})

    transport = httpx.MockTransport(handle_request)

    with EncarClient(
        transport=transport,
        sleep=delays.append,
        jitter=lambda _minimum, _maximum: 0.0,
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_json("/v1/missing")

    assert request_count == 1
    assert delays == []


def test_get_json_stops_after_max_attempts() -> None:
    request_count = 0
    delays: list[float] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(503, json={"message": "unavailable"})

    transport = httpx.MockTransport(handle_request)

    with EncarClient(
        transport=transport,
        sleep=delays.append,
        jitter=lambda _minimum, _maximum: 0.0,
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_json("/v1/test")

    assert request_count == 3
    assert delays == [1.0, 2.0]


def test_get_json_retries_timeout_then_succeeds() -> None:
    request_count = 0
    delays: list[float] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            raise httpx.ReadTimeout("timed out", request=request)

        return httpx.Response(200, json={"vehicleId": "12345"})

    transport = httpx.MockTransport(handle_request)

    with EncarClient(
        transport=transport,
        sleep=delays.append,
        jitter=lambda _minimum, _maximum: 0.0,
    ) as client:
        result = client.get_json("/v1/test")

    assert result == {"vehicleId": "12345"}
    assert request_count == 2
    assert delays == [1.0]


def test_get_json_applies_rate_limit_before_each_request() -> None:
    now = 0.0
    delays: list[float] = []

    def clock() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        delays.append(seconds)
        now += seconds

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"vehicleId": "12345"})

    rate_limiter = RateLimiter(
        requests_per_second=1.0,
        clock=clock,
        sleep=sleep,
    )
    transport = httpx.MockTransport(handle_request)

    with EncarClient(transport=transport, rate_limiter=rate_limiter) as client:
        client.get_json("/v1/first")
        client.get_json("/v1/second")

    assert delays == [1.0]


def test_get_json_logs_retry_and_success(caplog: pytest.LogCaptureFixture) -> None:
    request_count = 0
    logger = logging.getLogger("test.http_client")

    def handle_request(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            return httpx.Response(500, json={"private": "do-not-log"})

        return httpx.Response(200, json={"vehicleId": "12345"})

    transport = httpx.MockTransport(handle_request)

    with caplog.at_level(logging.INFO, logger=logger.name):
        with EncarClient(
            transport=transport,
            sleep=lambda _seconds: None,
            jitter=lambda _minimum, _maximum: 0.0,
            logger=logger,
        ) as client:
            client.get_json("/v1/test", params={"vehicleNo": "do-not-log"})

    events = [getattr(record, "event", None) for record in caplog.records]
    combined_messages = " ".join(record.getMessage() for record in caplog.records)

    assert events == [
        "http_request_started",
        "http_request_retry_scheduled",
        "http_request_started",
        "http_request_completed",
    ]
    assert "do-not-log" not in combined_messages
