# (Experimental) memecoin-trader

Personal Solana memecoin tracker (and eventually, trader). See [`CLAUDE.md`](./CLAUDE.md) for the full design and build plan, and [`docs/decisions.md`](./docs/decisions.md) for the current values of drift-prone facts (pricing, thresholds, program IDs).

## Prerequisites

- Docker (Desktop or engine) — for TimescaleDB.
- [`uv`](https://docs.astral.sh/uv/) — installs its own Python 3.12 from the workspace's `requires-python`.

## Quick start (phase 1)

```sh
# 1. Environment
cp .env.example .env
# fill in HELIUS_API_KEY (get one free at https://dashboard.helius.dev)

# 2. TimescaleDB — schema in db/migrations/ runs on first boot
docker compose up -d timescaledb

# 3. Python workspace (--all-packages installs every workspace member,
# not just the root)
uv sync --all-packages

# 4. Ingestor (phase 1 stub: schema-check then idle)
uv run python -m ingestor
```

## Layout

See [`CLAUDE.md`](./CLAUDE.md) §6.
