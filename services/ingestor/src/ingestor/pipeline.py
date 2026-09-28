from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass

import asyncpg

from decoder.programs import PUMPFUN_PROGRAM_ID
from decoder.pumpfun import parse_pumpfun_swap
from shared.config import HeliusConfig

from ingestor.enhance import HeliusEnhanced
from ingestor.persistence import TradeWriter
from ingestor.stream import stream_pumpfun_logs

log = logging.getLogger(__name__)


@dataclass
class Metrics:
    signatures_seen: int = 0
    signatures_ok: int = 0
    fetched: int = 0
    pumpfun_swaps: int = 0
    parsed: int = 0
    persisted: int = 0
    parse_failures: int = 0

    def reset(self) -> None:
        for f in self.__dataclass_fields__:
            setattr(self, f, 0)


async def run_pipeline(
    pool: asyncpg.Pool,
    helius_cfg: HeliusConfig,
    batch_size: int = 25,
    report_interval: float = 10.0,
) -> None:
    enhanced = HeliusEnhanced(helius_cfg.api_key, base_url=helius_cfg.enhanced_api_base)
    writer = TradeWriter(pool)
    metrics = Metrics()
    last_report = time.monotonic()

    stream = stream_pumpfun_logs(helius_cfg.ws_url, PUMPFUN_PROGRAM_ID)
    pending: list[str] = []
    try:
        async with contextlib.aclosing(stream):
            async for notif in stream:
                metrics.signatures_seen += 1
                if notif.err is None:
                    metrics.signatures_ok += 1
                    pending.append(notif.signature)

                if len(pending) >= batch_size:
                    await _process_batch(pending, enhanced, writer, metrics)
                    pending = []

                now = time.monotonic()
                if now - last_report >= report_interval:
                    log.info(
                        "pipeline: seen=%d ok=%d fetched=%d pumpfun=%d parsed=%d persisted=%d parse_fail=%d (%.1fs)",
                        metrics.signatures_seen,
                        metrics.signatures_ok,
                        metrics.fetched,
                        metrics.pumpfun_swaps,
                        metrics.parsed,
                        metrics.persisted,
                        metrics.parse_failures,
                        now - last_report,
                    )
                    metrics.reset()
                    last_report = now
    finally:
        await enhanced.close()


async def _process_batch(
    sigs: list[str],
    enhanced: HeliusEnhanced,
    writer: TradeWriter,
    metrics: Metrics,
) -> None:
    try:
        txs = await enhanced.fetch_transactions(sigs[: HeliusEnhanced.MAX_BATCH])
    except Exception as exc:
        log.warning("enhanced fetch failed (%s: %s)", type(exc).__name__, exc)
        return

    metrics.fetched += len(txs)
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        if tx.get("source") != "PUMP_FUN" or tx.get("type") != "SWAP":
            continue
        metrics.pumpfun_swaps += 1

        event = parse_pumpfun_swap(tx)
        if event is None:
            metrics.parse_failures += 1
            log.debug("parse failure: sig=%s", tx.get("signature"))
            continue
        metrics.parsed += 1

        try:
            if await writer.record_trade(event):
                metrics.persisted += 1
        except Exception as exc:
            log.warning(
                "persist failed (%s: %s) sig=%s",
                type(exc).__name__, exc, event.signature,
            )
