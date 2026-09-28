from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()

QUEUE_MAXSIZE = 200


@router.websocket("/ws/trades")
async def ws_trades(websocket: WebSocket) -> None:
    await websocket.accept()
    subscribers: set[asyncio.Queue[str]] = websocket.app.state.subscribers
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    subscribers.add(queue)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        pass
    finally:
        subscribers.discard(queue)
