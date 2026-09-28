from __future__ import annotations

from typing import Any

import httpx


class HeliusEnhanced:
    """Thin async wrapper around Helius Enhanced Transactions REST API."""

    MAX_BATCH = 100

    def __init__(self, api_key: str, base_url: str = "https://api.helius.xyz/v0"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_transactions(self, signatures: list[str]) -> list[dict[str, Any]]:
        if not signatures:
            return []
        if len(signatures) > self.MAX_BATCH:
            raise ValueError(f"batch too large ({len(signatures)} > {self.MAX_BATCH})")
        resp = await self._client.post(
            f"{self._base_url}/transactions",
            params={"api-key": self._api_key},
            json={"transactions": signatures},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
