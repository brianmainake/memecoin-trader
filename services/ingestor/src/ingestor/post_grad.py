from __future__ import annotations

import asyncio
import logging

import asyncpg

from decoder.pumpfun import parse_swap
from shared.config import HeliusConfig

from ingestor.enhance import HeliusEnhanced
from ingestor.persistence import TradeWriter

log = logging.getLogger(__name__)


async def run_poller(
    pool: asyncpg.Pool,
    helius_cfg: HeliusConfig,
    poll_interval: float = 60.0,
    batch_size: int = 20,
    tx_limit: int = 20,
    activity_window: str = "24 hours",
) -> None:
    """Pull recent post-graduation SWAPs for graduated tokens and persist them.

    Complements the main pump.fun WebSocket pipeline: bonding trades come
    in live via logsSubscribe; graduated tokens no longer trade against the
    pump.fun program, so we poll Helius's per-address SWAP feed and index
    every non-PUMP_FUN swap we find.
    """
    enhanced = HeliusEnhanced(helius_cfg.api_key, base_url=helius_cfg.enhanced_api_base)
    writer = TradeWriter(pool)
    try:
        while True:
            try:
                await _tick(pool, enhanced, writer, batch_size, tx_limit, activity_window)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.warning("post-grad poller (%s): %s", type(exc).__name__, exc)
            await asyncio.sleep(poll_interval)
    finally:
        await enhanced.close()


async def _tick(
    pool: asyncpg.Pool,
    enhanced: HeliusEnhanced,
    writer: TradeWriter,
    batch_size: int,
    tx_limit: int,
    activity_window: str,
) -> None:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT mint
              FROM tokens
             WHERE status = 'graduated'
               AND graduated_at > now() - interval '{activity_window}'
             ORDER BY graduated_at DESC
             LIMIT $1
            """,
            batch_size,
        )
    if not rows:
        return
    log.info(
        "post-grad: fetching post-graduation swaps for %d graduated tokens",
        len(rows),
    )

    persisted = 0
    parse_failures = 0
    for row in rows:
        mint = row["mint"]
        await asyncio.sleep(0.25)  # pace requests
        try:
            txs = await enhanced.address_transactions(mint, tx_type="SWAP", limit=tx_limit)
        except Exception as exc:
            log.warning("post-grad fetch %s: %s", mint, exc)
            continue

        for tx in txs:
            if not isinstance(tx, dict):
                continue
            source = tx.get("source")
            if source == "PUMP_FUN":
                continue  # bonding-phase trades handled by the live pipeline
            event = parse_swap(tx)
            if event is None:
                parse_failures += 1
                continue
            if event.mint != mint:
                # Aggregator tx may involve multiple mints; only index the one
                # we asked about to avoid double-counting under a different
                # graduated mint's address_transactions later.
                continue
            try:
                if await writer.record_trade(event):
                    persisted += 1
            except Exception as exc:
                log.warning("post-grad persist %s: %s", event.signature, exc)

    if persisted or parse_failures:
        log.info(
            "post-grad tick: persisted=%d parse_fail=%d across %d tokens",
            persisted, parse_failures, len(rows),
        )
