from __future__ import annotations

from typing import Annotated, Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_pool

router = APIRouter()

Interval = Literal["1m", "5m", "1h", "24h"]
_CANDLE_VIEW: dict[Interval, str] = {
    "1m": "trades_1m",
    "5m": "trades_5m",
    "1h": "trades_1h",
    "24h": "trades_24h",
}


@router.get("/tokens")
async def list_tokens(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[Literal["volume", "recent"], Query()] = "volume",
) -> list[dict[str, Any]]:
    order = {
        "volume": "s.volume_sol_lamports DESC NULLS LAST, t.mint",
        "recent": "s.last_trade_time DESC NULLS LAST, t.mint",
    }[sort]
    sql = f"""
        WITH stats AS (
            SELECT
                mint,
                count(*)                                       AS trade_count,
                count(*) FILTER (WHERE side = 'buy')           AS buy_count,
                count(*) FILTER (WHERE side = 'sell')          AS sell_count,
                sum(sol_lamports)::text                        AS volume_sol_lamports,
                max(time)                                      AS last_trade_time,
                (array_agg(price_sol ORDER BY time DESC))[1]::text AS last_price_sol
            FROM trades
            WHERE time > now() - interval '24 hours'
            GROUP BY mint
        )
        SELECT
            t.mint, t.symbol, t.name, t.status, t.decimals,
            s.trade_count, s.buy_count, s.sell_count,
            s.volume_sol_lamports, s.last_trade_time, s.last_price_sol
        FROM tokens t
        LEFT JOIN stats s ON s.mint = t.mint
        ORDER BY {order}
        LIMIT $1 OFFSET $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit, offset)
    return [dict(r) for r in rows]


@router.get("/tokens/{mint}")
async def get_token(
    mint: str,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT mint, symbol, name, decimals, status, created_at, "
            "graduated_at, pool_address, curve_address FROM tokens WHERE mint = $1",
            mint,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="token not found")
    return dict(row)


@router.get("/tokens/{mint}/candles")
async def get_candles(
    mint: str,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    interval: Annotated[Interval, Query()] = "1m",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    view = _CANDLE_VIEW[interval]
    sql = f"""
        SELECT
            bucket AS time,
            open::text  AS open,
            high::text  AS high,
            low::text   AS low,
            close::text AS close,
            volume_sol_lamports::text AS volume_sol_lamports,
            buy_count, sell_count, trade_count
        FROM {view}
        WHERE mint = $1
        ORDER BY bucket DESC
        LIMIT $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, mint, limit)
    return [dict(r) for r in rows]


@router.get("/tokens/{mint}/trades")
async def get_trades(
    mint: str,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            time, signature, slot, wallet, side,
            sol_lamports::text  AS sol_lamports,
            token_base_units::text AS token_base_units,
            price_sol::text     AS price_sol,
            venue
        FROM trades
        WHERE mint = $1
        ORDER BY time DESC
        LIMIT $2
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, mint, limit)
    return [dict(r) for r in rows]
