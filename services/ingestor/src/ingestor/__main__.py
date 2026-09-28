import asyncio
import logging
import os
import sys
import time

import asyncpg

from decoder.programs import PUMPFUN_PROGRAM_ID
from shared.config import DatabaseConfig, HeliusConfig, load_dotenv

from ingestor.stream import stream_pumpfun_logs

log = logging.getLogger("ingestor")


async def run() -> None:
    load_dotenv()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    db_cfg = DatabaseConfig.from_env()
    helius_cfg = HeliusConfig.from_env()

    conn = await asyncpg.connect(db_cfg.dsn)
    try:
        row = await conn.fetchrow("SELECT to_regclass('public.trades') AS trades_tbl")
        if not row or row["trades_tbl"] is None:
            raise RuntimeError("trades table missing; run db migrations first")
    finally:
        await conn.close()

    log.info("schema ok; subscribing to pump.fun program=%s", PUMPFUN_PROGRAM_ID)
    await _log_stream_loop(helius_cfg)


async def _log_stream_loop(helius_cfg: HeliusConfig) -> None:
    received = 0
    successful = 0
    last_report = time.monotonic()
    report_interval = 10.0

    async for notif in stream_pumpfun_logs(helius_cfg.ws_url, PUMPFUN_PROGRAM_ID):
        received += 1
        if notif.err is None:
            successful += 1
        now = time.monotonic()
        if now - last_report >= report_interval:
            log.info(
                "logs: received=%d successful=%d in %.1fs; latest sig=%s slot=%d",
                received, successful, now - last_report, notif.signature, notif.slot,
            )
            received = 0
            successful = 0
            last_report = now


def entrypoint() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except RuntimeError as exc:
        log.error("%s", exc)
        sys.exit(2)


if __name__ == "__main__":
    entrypoint()
