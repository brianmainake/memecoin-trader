from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path

from decoder.programs import PUMPFUN_PROGRAM_ID
from shared.config import HeliusConfig

from ingestor.enhance import HeliusEnhanced
from ingestor.stream import stream_pumpfun_logs

log = logging.getLogger(__name__)


async def capture(
    helius_cfg: HeliusConfig,
    target_count: int,
    out_dir: Path,
    batch_size: int = 5,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("capture: writing to %s (target=%d)", out_dir, target_count)

    enhanced = HeliusEnhanced(helius_cfg.api_key, base_url=helius_cfg.enhanced_api_base)
    captured = 0
    pending: list[str] = []
    stream = stream_pumpfun_logs(helius_cfg.ws_url, PUMPFUN_PROGRAM_ID)
    try:
        async with contextlib.aclosing(stream):
            async for notif in stream:
                if notif.err is not None:
                    continue
                pending.append(notif.signature)
                if len(pending) < batch_size:
                    continue

                batch = pending[: HeliusEnhanced.MAX_BATCH]
                pending = pending[len(batch):]
                try:
                    txs = await enhanced.fetch_transactions(batch)
                except Exception as exc:
                    log.warning("enhanced fetch failed (%s: %s)", type(exc).__name__, exc)
                    continue

                for tx in txs:
                    if not isinstance(tx, dict):
                        continue
                    sig = tx.get("signature")
                    if not sig:
                        continue
                    (out_dir / f"{sig}.json").write_text(json.dumps(tx, indent=2, sort_keys=True))
                    captured += 1
                    log.info("captured %d/%d: %s", captured, target_count, sig)
                    if captured >= target_count:
                        return captured
    finally:
        await enhanced.close()
    return captured
