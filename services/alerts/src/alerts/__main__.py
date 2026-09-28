import asyncio
import json
import logging
import os
import sys

import asyncpg

from shared.config import DatabaseConfig, load_dotenv

from alerts.delivery import LogDelivery
from alerts.engine import AlertEngine

log = logging.getLogger("alerts")


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def run() -> None:
    load_dotenv()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    dsn = DatabaseConfig.from_env().dsn

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, init=_init_conn)
    listener = await asyncpg.connect(dsn)
    try:
        engine = AlertEngine(pool, listener, LogDelivery())
        log.info("alert engine starting")
        await engine.run()
    finally:
        await listener.close()
        await pool.close()


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
