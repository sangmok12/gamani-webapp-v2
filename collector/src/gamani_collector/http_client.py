import random
import time
from collections.abc import Callable
from typing import Any

import httpx


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
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self._max_attempts = max_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self._sleep = sleep
        self._jitter = jitter
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
        response: httpx.Response | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(path, params=params)
            except (httpx.ConnectError, httpx.TimeoutException):
                if attempt == self._max_attempts:
                    raise

                self._wait_before_retry(attempt)
                continue

            if self._is_retryable_status(response.status_code) and attempt < self._max_attempts:
                self._wait_before_retry(attempt)
                continue

            response.raise_for_status()
            break

        if response is None:
            raise RuntimeError("HTTP request completed without a response")

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("API response must be a JSON object")

        return data

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599

    def _wait_before_retry(self, attempt: int) -> None:
        delay = self._backoff_base_seconds * (2 ** (attempt - 1))
        delay += self._jitter(0.0, 0.25)
        self._sleep(delay)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EncarClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
