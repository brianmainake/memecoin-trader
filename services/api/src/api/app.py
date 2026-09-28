from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import DatabaseConfig, load_dotenv

from api.routes import tokens, websocket

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()
    dsn = DatabaseConfig.from_env().dsn
    app.state.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=8)
    app.state.subscribers = set()
    app.state.listener_conn = await asyncpg.connect(dsn)

    def _on_notify(conn: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
        dropped = 0
        for q in app.state.subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dropped += 1
        if dropped:
            log.warning("dropped %d notifications for slow subscribers", dropped)

    await app.state.listener_conn.add_listener("trade_events", _on_notify)
    log.info("listening on trade_events; %d subscribers", len(app.state.subscribers))

    try:
        yield
    finally:
        await app.state.listener_conn.remove_listener("trade_events", _on_notify)
        await app.state.listener_conn.close()
        await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="memecoin-trader API", version="0.0.1", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(tokens.router, prefix="/api")
    app.include_router(websocket.router, prefix="/api")

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
