import asyncio
import logging
import os
import sys

import asyncpg

from shared.config import DatabaseConfig

log = logging.getLogger("ingestor")


async def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = DatabaseConfig.from_env()
    log.info("connecting to database")
    conn = await asyncpg.connect(cfg.dsn)
    try:
        row = await conn.fetchrow("SELECT to_regclass('public.trades') AS trades_tbl")
        if not row or row["trades_tbl"] is None:
            log.error("trades table missing; run db migrations first")
            sys.exit(2)
        log.info("schema ok; stream subscriber not implemented yet, idling")
        while True:
            await asyncio.sleep(60)
    finally:
        await conn.close()


def entrypoint() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    entrypoint()
