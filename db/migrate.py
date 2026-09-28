#!/usr/bin/env python3
"""Apply pending SQL migrations to DATABASE_URL.

Usage: uv run python db/migrate.py

Migrations are tracked in the schema_migrations table. On first run against
a database that was bootstrapped by docker-entrypoint-initdb.d (so 0001 is
already applied), the runner detects the pre-existing 'trades' table and
records 0001_initial as applied without re-running it.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("no migrations found")
        return 0

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )

        recorded = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
        trades_exists = await conn.fetchval("SELECT to_regclass('public.trades') IS NOT NULL")
        first_version = files[0].stem
        if trades_exists and first_version not in recorded:
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                first_version,
            )
            recorded.add(first_version)
            print(f"bootstrap: marked {first_version} as already applied")

        for f in files:
            version = f.stem
            if version in recorded:
                print(f"skip   {version}")
                continue
            print(f"apply  {version}")
            sql = f.read_text()
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version,
                )
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
