import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from gamani_collector.rate_limiter import RateLimiter


@dataclass(frozen=True)
class HttpResult:
    data: dict[str, Any]
    status_code: int
    attempt_count: int
    elapsed_ms: int


class EncarClient:
    """엔카 API와 통신하는 공통 HTTP 클라이언트."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.encar.com",
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
        rate_limiter: RateLimiter | None = None,
        logger: logging.Logger | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self._max_attempts = max_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._rate_limiter = rate_limiter
        self._logger = logger or logging.getLogger(__name__)
        self._clock = clock
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={
                "Accept": "application/json",
                "User-Agent": "gamani-collector/0.1.0",
            },
            transport=transport,
        )

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self.get_json_result(path, params=params).data

    def get_json_result(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> HttpResult:
        response: httpx.Response | None = None
        completed_attempt = 0
        completed_elapsed_ms = 0

        for attempt in range(1, self._max_attempts + 1):
            if self._rate_limiter is not None:
                self._rate_limiter.wait()

            started_at = self._clock()
            self._logger.info(
                "HTTP request started",
                extra={"event": "http_request_started", "path": path, "attempt": attempt},
            )

            try:
                response = self._client.get(path, params=params)
            except (httpx.ConnectError, httpx.TimeoutException) as error:
                elapsed_ms = round((self._clock() - started_at) * 1000)

                if attempt == self._max_attempts:
                    self._logger.error(
                        "HTTP request failed",
                        extra={
                            "event": "http_request_failed",
                            "path": path,
                            "attempt": attempt,
                            "elapsed_ms": elapsed_ms,
                            "error_type": type(error).__name__,
                        },
                    )
                    raise

                retry_delay = self._retry_delay(attempt)
                self._logger.warning(
                    "HTTP request will be retried",
                    extra={
                        "event": "http_request_retry_scheduled",
                        "path": path,
                        "attempt": attempt,
                        "elapsed_ms": elapsed_ms,
                        "retry_delay_seconds": retry_delay,
                        "error_type": type(error).__name__,
                    },
                )
                self._sleep(retry_delay)
                continue

            if self._is_retryable_status(response.status_code) and attempt < self._max_attempts:
                retry_delay = self._retry_delay(attempt)
                self._logger.warning(
                    "HTTP request will be retried",
                    extra={
                        "event": "http_request_retry_scheduled",
                        "path": path,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "elapsed_ms": round((self._clock() - started_at) * 1000),
                        "retry_delay_seconds": retry_delay,
                    },
                )
                self._sleep(retry_delay)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                self._logger.error(
                    "HTTP request failed",
                    extra={
                        "event": "http_request_failed",
                        "path": path,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "elapsed_ms": round((self._clock() - started_at) * 1000),
                    },
                )
                raise

            completed_attempt = attempt
            completed_elapsed_ms = round((self._clock() - started_at) * 1000)
            self._logger.info(
                "HTTP request completed",
                extra={
                    "event": "http_request_completed",
                    "path": path,
                    "status_code": response.status_code,
                    "attempt": attempt,
                    "elapsed_ms": completed_elapsed_ms,
                },
            )
            break

        if response is None:
            raise RuntimeError("HTTP request completed without a response")

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("API response must be a JSON object")

        return HttpResult(
            data=data,
            status_code=response.status_code,
            attempt_count=completed_attempt,
            elapsed_ms=completed_elapsed_ms,
        )

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599

    def _retry_delay(self, attempt: int) -> float:
        delay = self._backoff_base_seconds * (2 ** (attempt - 1))
        delay += self._jitter(0.0, 0.25)
        return delay

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EncarClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
