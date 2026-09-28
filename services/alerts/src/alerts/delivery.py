from __future__ import annotations

import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Delivery(Protocol):
    async def send(self, message: str, meta: dict[str, Any]) -> None: ...


class LogDelivery:
    """Prints to stdout via the logger. Placeholder until Telegram lands."""

    async def send(self, message: str, meta: dict[str, Any]) -> None:
        rule = meta.get("type", "?")
        mint = meta.get("mint", "?")
        log.info("ALERT [%s | %s]: %s", rule, mint, message)
