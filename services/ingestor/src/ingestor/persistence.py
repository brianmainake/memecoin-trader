from __future__ import annotations

import json

import asyncpg

from shared.events import TradeEvent


class TradeWriter:
    """Upsert tokens, insert trades, and emit pg_notify('trade_events', ...)."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def record_trade(self, event: TradeEvent) -> bool:
        payload = _notify_payload(event)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO tokens (mint, decimals)
                    VALUES ($1, $2)
                    ON CONFLICT (mint) DO NOTHING
                    """,
                    event.mint,
                    event.token_decimals,
                )
                result = await conn.execute(
                    """
                    INSERT INTO trades (
                        time, signature, event_index, slot, mint, wallet, side,
                        sol_lamports, token_base_units, price_sol, sol_usd, venue
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (signature, event_index, time) DO NOTHING
                    """,
                    event.time,
                    event.signature,
                    event.event_index,
                    event.slot,
                    event.mint,
                    event.wallet,
                    event.side.value,
                    event.sol_lamports,
                    event.token_base_units,
                    event.price_sol,
                    event.sol_usd,
                    event.venue.value,
                )
                inserted = result.split()[-1] == "1"
                if inserted:
                    await conn.execute("SELECT pg_notify('trade_events', $1)", payload)
        return inserted


def _notify_payload(event: TradeEvent) -> str:
    return json.dumps(
        {
            "signature": event.signature,
            "slot": event.slot,
            "mint": event.mint,
            "wallet": event.wallet,
            "side": event.side.value,
            "sol_lamports": str(event.sol_lamports),
            "token_base_units": str(event.token_base_units),
            "time": event.time.isoformat(),
        },
        separators=(",", ":"),
    )
