# Decisions log

Ambient, drift-prone facts. Every **VERIFY** bullet in `CLAUDE.md` should resolve to a line here with a source and a date. Update whenever a value changes; do not let this file rot.

## Solana

- **Ingest commitment level:** `confirmed` — 2026-09-27. Source: CLAUDE.md §4.1.
- **Executor pre-trade commitment level:** `finalized` — 2026-09-27. Source: CLAUDE.md §4.1.
- **pump.fun program ID:** _unverified_ — look up at build time from the official docs before the first decoder is written.
- **pump.fun graduation threshold (SOL raised):** _unverified_ — historically reported around 85 SOL; confirm from on-chain curve state before relying on it.
- **DEX pump.fun migrates into:** believed to be PumpSwap (formerly Raydium routing). _Unverified_ — confirm before the executor is wired up.

## Providers

- **Stream provider:** Helius — 2026-09-27. Free tier for phase 1; upgrade to Standard ($49/mo) or Dev ($99/mo) once event volume warrants. Verify current pricing at https://helius.dev/pricing before upgrading — pricing changes.
- **SOL/USD source:** _pending_ — choose between Pyth (on-chain, low latency) and CoinGecko (off-chain, simple HTTP). Decision required before continuous aggregates go live.

## Ingest scope

- **Watched-token promotion rule:** `cumulative_volume_sol > 5 OR status = 'graduated'` — 2026-09-27. Initial value; tune after the first week of live data.

## Runtime

- **Deployment target:** local (macOS, Docker Desktop) — 2026-09-27. Migration to VPS (Hetzner CX22, ~€5/mo) is deferred until always-on alerts are required.
- **Python version:** 3.12 (fetched by `uv` per `requires-python`) — 2026-09-27.
- **TimescaleDB image tag:** `timescale/timescaledb:latest-pg16` — 2026-09-27. Floats the Timescale minor; pin explicitly if reproducibility becomes an issue.
