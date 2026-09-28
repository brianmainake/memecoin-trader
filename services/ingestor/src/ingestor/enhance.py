from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

log = logging.getLogger(__name__)


class HeliusEnhanced:
    """Thin async wrapper around Helius Enhanced Transactions REST API.

    Retries on 429 with exponential backoff + jitter. Free-tier limits are
    tight; callers should also increase batch size and reduce request rate.
    """

    MAX_BATCH = 100
    _RETRY_ATTEMPTS = 4
    _RETRY_BASE_DELAY = 0.5

    def __init__(self, api_key: str, base_url: str = "https://api.helius.xyz/v0"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_transactions(self, signatures: list[str]) -> list[dict[str, Any]]:
        if not signatures:
            return []
        if len(signatures) > self.MAX_BATCH:
            raise ValueError(f"batch too large ({len(signatures)} > {self.MAX_BATCH})")

        delay = self._RETRY_BASE_DELAY
        last_resp: httpx.Response | None = None
        for _ in range(self._RETRY_ATTEMPTS):
            resp = await self._client.post(
                f"{self._base_url}/transactions",
                params={"api-key": self._api_key},
                json={"transactions": signatures},
            )
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp.json()
            last_resp = resp
            await asyncio.sleep(delay + random.random() * 0.25)
            delay = min(delay * 2, 8.0)
        assert last_resp is not None
        last_resp.raise_for_status()
        return []

    async def close(self) -> None:
        await self._client.aclose()
