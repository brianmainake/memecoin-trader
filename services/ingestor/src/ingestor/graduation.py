from __future__ import annotations

import asyncio
import logging

import asyncpg

from shared.config import HeliusConfig

from ingestor.enhance import HeliusEnhanced

log = logging.getLogger(__name__)


async def check_graduation(enhanced: HeliusEnhanced, mint: str) -> str | None:
    """Return the non-PUMP_FUN source name if this mint has post-graduation
    swap activity, else None. A bonding-only token only ever swaps via
    PUMP_FUN; the moment any SWAP on the mint reports a different source
    (PUMP_AMM, PUMPSWAP, RAYDIUM_AMM, JUPITER_AGGREGATOR, ...) the curve
    has migrated and the token trades on a real DEX.
    """
    try:
        txs = await enhanced.address_transactions(mint, tx_type="SWAP", limit=10)
    except Exception as exc:
        log.warning("graduation check %s: %s", mint, exc)
        return None
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        source = tx.get("source")
        if source and source != "PUMP_FUN":
            return source
    return None


async def run_poller(
    pool: asyncpg.Pool,
    helius_cfg: HeliusConfig,
    poll_interval: float = 300.0,
    batch_size: int = 30,
    activity_window: str = "2 hours",
) -> None:
    enhanced = HeliusEnhanced(helius_cfg.api_key, base_url=helius_cfg.enhanced_api_base)
    try:
        while True:
            try:
                await _tick(pool, enhanced, batch_size, activity_window)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.warning("graduation poller (%s): %s", type(exc).__name__, exc)
            await asyncio.sleep(poll_interval)
    finally:
        await enhanced.close()


async def _tick(
    pool: asyncpg.Pool,
    enhanced: HeliusEnhanced,
    batch_size: int,
    activity_window: str,
) -> None:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT DISTINCT t.mint
            FROM tokens t
            JOIN trades tr ON tr.mint = t.mint
            WHERE t.status = 'bonding'
              AND tr.time > now() - interval '{activity_window}'
            LIMIT $1
            """,
            batch_size,
        )
    if not rows:
        return
    log.info("graduation: checking %d bonding tokens active in last %s", len(rows), activity_window)

    graduated = 0
    for row in rows:
        mint = row["mint"]
        await asyncio.sleep(0.2)  # pace out requests to stay under free-tier limits
        source = await check_graduation(enhanced, mint)
        if source is None:
            continue
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE tokens
                   SET status = 'graduated', graduated_at = now()
                 WHERE mint = $1 AND status = 'bonding'
                """,
                mint,
            )
        if result.endswith(" 1"):
            graduated += 1
            log.info("graduated: mint=%s via %s", mint, source)
    if graduated:
        log.info("graduation tick: %d newly graduated (of %d checked)", graduated, len(rows))
