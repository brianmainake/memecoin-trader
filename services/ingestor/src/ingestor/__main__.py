import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

from decoder.programs import PUMPFUN_PROGRAM_ID
from shared.config import DatabaseConfig, HeliusConfig, load_dotenv

from ingestor.capture import capture
from ingestor.graduation import run_poller as run_graduation_poller
from ingestor.pipeline import run_pipeline

log = logging.getLogger("ingestor")


async def run(args: argparse.Namespace) -> None:
    load_dotenv()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    helius_cfg = HeliusConfig.from_env()

    if args.capture:
        n = await capture(helius_cfg, args.capture, args.capture_dir)
        log.info("capture complete: %d transactions written to %s", n, args.capture_dir)
        return

    db_cfg = DatabaseConfig.from_env()
    pool = await asyncpg.create_pool(db_cfg.dsn, min_size=1, max_size=4)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT to_regclass('public.trades') AS trades_tbl")
            if not row or row["trades_tbl"] is None:
                raise RuntimeError("trades table missing; run db migrations first")
        log.info("schema ok; starting pipeline + graduation poller (program=%s)", PUMPFUN_PROGRAM_ID)
        pipeline_task = asyncio.create_task(run_pipeline(pool, helius_cfg))
        graduation_task = asyncio.create_task(run_graduation_poller(pool, helius_cfg))
        try:
            done, _ = await asyncio.wait(
                {pipeline_task, graduation_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in done:
                task.result()  # re-raise if a task crashed
        finally:
            graduation_task.cancel()
            pipeline_task.cancel()
            await asyncio.gather(pipeline_task, graduation_task, return_exceptions=True)
    finally:
        await pool.close()


def entrypoint() -> None:
    parser = argparse.ArgumentParser(prog="ingestor")
    parser.add_argument(
        "--capture",
        type=int,
        metavar="N",
        help="Capture N pump.fun transactions to --capture-dir and exit.",
    )
    parser.add_argument(
        "--capture-dir",
        type=Path,
        default=Path("fixtures/live"),
        help="Where to write captured fixtures (default: fixtures/live).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    except RuntimeError as exc:
        log.error("%s", exc)
        sys.exit(2)


if __name__ == "__main__":
    entrypoint()
