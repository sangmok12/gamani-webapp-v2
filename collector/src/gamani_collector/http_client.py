from typing import Any

import httpx


class EncarClient:
    """엔카 API와 통신하는 공통 HTTP 클라이언트."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.encar.com",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
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
        response = self._client.get(path, params=params)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError("API response must be a JSON object")

        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EncarClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()