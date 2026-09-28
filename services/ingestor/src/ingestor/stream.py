from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LogNotification:
    signature: str
    slot: int
    err: Any


async def stream_pumpfun_logs(ws_url: str, program_id: str) -> AsyncIterator[LogNotification]:
    backoff = 1.0
    while True:
        try:
            async for notif in _connect_and_stream(ws_url, program_id):
                yield notif
                backoff = 1.0
        except (ConnectionClosed, WebSocketException, OSError, TimeoutError, RuntimeError) as exc:
            delay = min(backoff, 30.0) + random.uniform(0, 1.0)
            log.warning(
                "stream disconnected (%s: %s), reconnecting in %.1fs",
                type(exc).__name__, exc, delay,
            )
            await asyncio.sleep(delay)
            backoff = min(backoff * 2.0, 30.0)


async def _connect_and_stream(ws_url: str, program_id: str) -> AsyncIterator[LogNotification]:
    log.info("connecting to Solana WebSocket")
    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [program_id]},
                {"commitment": "confirmed"},
            ],
        }))
        ack_raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
        ack = json.loads(ack_raw)
        if "result" not in ack:
            raise RuntimeError(f"logsSubscribe failed: {ack}")
        log.info("subscribed to pump.fun logs (subscription=%s)", ack["result"])

        async for message in ws:
            payload = json.loads(message)
            params = payload.get("params")
            if not params:
                continue
            result = params.get("result", {})
            value = result.get("value", {})
            signature = value.get("signature")
            err = value.get("err")
            slot = result.get("context", {}).get("slot")
            if signature is None or slot is None:
                continue
            yield LogNotification(signature=signature, slot=slot, err=err)
