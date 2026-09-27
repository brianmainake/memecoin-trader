# CLAUDE.md: Personal Solana Token Tracker

Project context and build plan for Claude Code. Read this fully before writing code. Sections marked **VERIFY** contain facts that may be out of date and must be checked against current docs or on-chain data before being relied on.

## 1. What we're building

A **personal, single-user** tool for tracking and (eventually) trading memecoins on Solana. It is inspired by the fomo.family app (a social-first crypto trading app) but drops the social layer and focuses on:

1. A **dashboard** to track tokens: price, volume, trade count, buy vs sell, holders, bonding-curve progress, graduation status.
2. **Real-time alerts** (graduation, bonding progress, volume spikes, large trades, tracked wallets).
3. **Trading** from the dashboard, built last and isolated from everything else.

Non-goals (for now): multi-user accounts, a social feed, follower graphs, leaderboards, copy trading, other chains, mobile apps, custody of anyone else's funds.

The user is building this for themselves, so optimize for simplicity, low cost and a machine they control, not for scale.

## 2. Background: how the domain works

### Bonding curve and graduation
- On launchpads (pump.fun is the main one on Solana), anyone can create a token cheaply. New tokens start on a **bonding curve**: a smart contract sells the token directly and the price rises automatically as people buy. Traders trade against the contract, not each other. This is the "bonding" or "pre-bonded" stage.
- When enough has been bought into the curve (threshold set by the launchpad), the curve closes and the funds seed a real liquidity pool on a DEX. This is **graduation**. After that the token trades on the open market.
- Graduation only means a demand threshold was met. It is **not** a safety signal. Rug pulls, concentrated holders and sudden crashes still happen after graduation.
- **VERIFY:** which DEX pump.fun currently migrates into (believed to be PumpSwap, formerly Raydium), the current program addresses, the graduation threshold, and the curve account layout. Do not hardcode from memory.

### What can and can't be derived from the chain
- Every swap is public. Watching a known wallet's buys and sells needs no third party.
- Identity, follower graphs, leaderboards and accurate per-user PnL are app-layer concerns, not chain data. Not needed for this personal project.

### fomo.family reference (for feature inspiration only)
- Social crypto trading app by FOMO Labs Inc. Features: feed, follow traders, leaderboard, real-time alerts, gasless multichain swaps, Apple Pay funding, token discovery sections (Trending, Most Held, Graduated, Bonding/pre-bonded, Verified), watchlists, per-token analytics (liquidity, buy/sell volume, buyer/seller ratio, holders, top-holder concentration).
- Known complaints worth designing against: failed sells, slow execution on mobile, withdrawal friction, and users buying rug-pull tokens because the UI made it one tap.
- Note: fomo is social trading, not automatic copy trading.

## 3. Architecture

```
Solana network (pump.fun curves + graduated pools)
        |
Stream provider (Helius or Triton gRPC / Yellowstone)
        |
Ingestor (decode, normalize, dedupe)
        |
TimescaleDB (trades, candles, rules, cooldowns) --- pg_notify('trade_events')
        |                                                  |          |
API server (REST + WebSocket) ----> Dashboard         Alert engine (LISTEN)
        |                                                  |
Trade executor (isolated, capped hot wallet)          Telegram
        |
Swap routing (Jupiter / launchpad program)
```

Colour logic from the design diagram: everything except the executor is **read-only** and safe to build first. The executor **touches money**: build it last and keep it isolated.

### Design decisions
- **Single machine**, Docker Compose. Laptop or a small VPS (VPS preferred for alerts while the laptop is closed).
- **One database.** TimescaleDB (Postgres + time-series extension) holds trades, candles, watchlists and alert rules. Continuous aggregates produce 1m/5m/1h volume and buy/sell counts. No separate analytics store.
- **No Redis.** Live fan-out is Postgres `LISTEN/NOTIFY` (`pg_notify` from the ingestor; `LISTEN trade_events` in alert engine and API). In-process rolling windows for volume-spike detection. Add Redis only if fan-out actually hurts, which is unlikely for a single-user tool.
- **Provider stream, not a self-run node.** Use a gRPC/Geyser stream, not RPC polling (too slow). **VERIFY** current free-tier limits and pricing.
- **Telegram bot** for alerts (simplest for personal use).
- **Solana only, one launchpad first** (pump.fun and the pool it graduates into). Each additional venue multiplies decoder work.

### Language and stack
- **Python** for all backend services (ingestor, alert engine, API, executor). Async throughout: `asyncio`, `asyncpg` for Postgres (both queries and `LISTEN/NOTIFY`), `httpx` for HTTP, provider SDKs or `grpclib` for streams, `python-telegram-bot` for alerts. `uv` for env/deps.
- **Dashboard: Next.js** + TradingView `lightweight-charts`. Talks to the Python API over REST + WebSocket. Separate toolchain, separate deploy.
- Decoding: `solders` + `anchorpy` for Anchor IDLs; fall back to manual byte parsing where the launchpad ships no IDL.
- Tests: `pytest`; use real captured transactions as fixtures for the decoder.

## 4. Components

### 4.1 Ingestor
- Subscribes to the launchpad program and to the pools tokens migrate into (and to curve account updates for watched tokens).
- Decodes with the program IDLs into a normalized event stream. Event types: `token_created`, `buy`, `sell`, `curve_complete`, `graduated` (migration to pool), plus pool swaps after graduation.
- Dedupes by transaction signature. Ignores failed transactions. Default commitment is `confirmed` (fast, sub-second reorg risk is very low on Solana in practice); upgrade to `finalized` for the executor's pre-trade reads.
- Reconnects with backoff and replays from the last seen slot where the provider allows.
- Decoder lives in **its own isolated module**. Launchpads upgrade programs and decoders break. Log every transaction that cannot be parsed and alert on parse-failure rate so a silent break is visible.
- Writes each event to TimescaleDB and emits `pg_notify('trade_events', <compact json>)` for live consumers. Notifications carry only what a rule/UI needs to decide "do I care?" — full detail lives in the database.

### 4.2 Normalized trade schema (the key table, get this right)
One row per trade: signature, slot, block time, wallet, token mint, side (buy/sell), SOL amount, token amount, price, venue (curve or pool id). Everything else is derived from this.

Sketch (adjust as needed):

```sql
CREATE TABLE tokens (
  mint            TEXT PRIMARY KEY,
  symbol          TEXT,
  name            TEXT,
  decimals        SMALLINT NOT NULL,
  creator         TEXT,
  created_at      TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'bonding'
                  CHECK (status IN ('bonding','graduated')),
  graduated_at    TIMESTAMPTZ,
  pool_address    TEXT,
  curve_address   TEXT
);

-- Amounts stored as raw base units (lamports for SOL, 10^decimals for tokens).
-- Prices as SOL-per-token with wide precision for tiny memecoin prices.
-- sol_usd captured at trade time so historical USD values do not drift when
-- the price source updates.
CREATE TABLE trades (
  time              TIMESTAMPTZ NOT NULL,
  signature         TEXT NOT NULL,
  event_index       SMALLINT NOT NULL DEFAULT 0,
  slot              BIGINT NOT NULL,
  mint              TEXT NOT NULL,
  wallet            TEXT NOT NULL,
  side              TEXT NOT NULL CHECK (side IN ('buy','sell')),
  sol_lamports      NUMERIC(40, 0) NOT NULL,
  token_base_units  NUMERIC(40, 0) NOT NULL,
  price_sol         NUMERIC(40, 20) NOT NULL,
  sol_usd           NUMERIC(20, 8),
  venue             TEXT NOT NULL CHECK (venue IN ('curve','pool')),
  PRIMARY KEY (signature, event_index)
);
SELECT create_hypertable('trades', 'time');
CREATE INDEX ON trades (mint, time DESC);
CREATE INDEX ON trades (wallet, time DESC);

CREATE TABLE curve_snapshots (
  time                 TIMESTAMPTZ NOT NULL,
  mint                 TEXT NOT NULL,
  real_sol_reserves    NUMERIC(40, 0),
  real_token_reserves  NUMERIC(40, 0),
  progress_pct         NUMERIC(6, 3),
  PRIMARY KEY (mint, time)
);
SELECT create_hypertable('curve_snapshots', 'time');

CREATE TABLE watchlist (
  mint     TEXT PRIMARY KEY,
  added_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tracked_wallets (
  wallet TEXT PRIMARY KEY,
  label  TEXT
);

CREATE TABLE alert_rules (
  id                SERIAL PRIMARY KEY,
  type              TEXT NOT NULL,
  params            JSONB NOT NULL,
  enabled           BOOLEAN DEFAULT true,
  cooldown_seconds  INT DEFAULT 300
);

-- Per-(rule, mint) cooldown so a busy token cannot spam a single rule.
CREATE TABLE alert_cooldowns (
  rule_id       INT NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
  mint          TEXT NOT NULL,
  last_fired_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (rule_id, mint)
);

CREATE TABLE alert_log (
  id        BIGSERIAL PRIMARY KEY,
  rule_id   INT,
  mint      TEXT,
  fired_at  TIMESTAMPTZ DEFAULT now(),
  payload   JSONB
);
```

Continuous aggregates over `trades` for 1m, 5m, 1h and 24h: OHLC price, total volume, buy count, sell count, buy volume, sell volume. **Aggregates are for dashboard reads.** They refresh on a schedule and lag by seconds-to-minutes — the alert engine must not read from them. Live volume for spike detection is a per-mint rolling deque of recent trades held in the alert-engine process (see §4.4).

### 4.3 Derived metrics for the dashboard
- Volume, buy/sell counts and buy/sell ratio over 1m, 5m, 1h, 24h windows.
- OHLCV candles.
- **Bonding progress:** compute from the curve account's reserves (not by counting trades) and compare against the curve's completion target. **VERIFY** the account layout and target.
- **Graduation:** detect the migration event, flip `tokens.status`, record the pool address, and start indexing the new pool.
- **Holders and top-holder concentration:** hardest part (needs token-account snapshots). Use a provider API at first (e.g. Helius or Birdeye). Do not build it yourself early.
- USD values: capture SOL/USD into `trades.sol_usd` at ingest time from a single source (Pyth on-chain or CoinGecko), recorded in `docs/decisions.md`. Do not convert at query time — historical dollar values must not shift when the source updates.

### 4.4 Alert engine
- Consumes trade events via Postgres `LISTEN trade_events` and evaluates rules **in memory as events arrive** (not on a schedule). Rules loaded from `alert_rules`; cooldown state loaded from `alert_cooldowns` at startup, cached in memory, and written back on every fire.
- Starter rule types:
  - `graduated`: a watched or any token graduates
  - `bonding_progress`: crosses a threshold (e.g. 80%)
  - `volume_spike`: rolling-window volume exceeds N times its recent baseline; the window is a per-mint deque in the engine process, not a continuous aggregate
  - `large_trade`: single buy or sell above a size
  - `wallet_trade`: a tracked wallet trades
- **Per-(rule, mint) cooldown from day one** via `alert_cooldowns` (composite key on rule + token), or busy tokens will spam a single rule.
- Delivery: Telegram bot. Keep a delivery interface so other channels can be added.
- Log every fired alert to `alert_log`.

### 4.5 API server
- REST for history (tokens, candles, trades, watchlist, rules).
- WebSocket for live token stats and alerts.
- Talks to TimescaleDB directly and subscribes via `LISTEN trade_events` for live pushes to WebSocket clients. Calls the executor over a local internal interface for trades.

### 4.6 Dashboard (Next.js)
- Token list with sections: Trending, Bonding, Graduated, Watchlist. Filters and sorting by volume, age, progress.
- Token detail page: candles (lightweight-charts), volume, buy vs sell, bonding progress bar, graduation status, recent trades, holder concentration, links to explorer.
- Alerts view and rule editor.
- Trade panel (added in the final phase).

### 4.7 Trade executor (build last)
This is the only component that holds a key. Treat it as high-risk.

- **Separate process**, separate wallet: a fresh keypair holding only funds the user is willing to lose. It shares no keys with any other service.
- Key storage: environment secret or OS keychain. **Never** in the database, in the repo, or in logs.
- **Guardrails in code (non-negotiable):** max size per trade, daily spend cap, slippage limit, simulate-before-send, and **manual confirmation** for every trade from the dashboard. No autonomous trading.
- **Kill switch:** the executor checks a sentinel (`EXECUTOR_HALT=1` env var or a file at `/var/lib/memecoin-trader/HALT`) before every send. Present → refuse all trades and log. One-touch stop if anything looks wrong. There is no runtime override for this flag; toggling requires filesystem/env access, deliberately.
- **Key at rest, honest note:** on the laptop, macOS Keychain gives a real user prompt. On an unattended VPS, any keyring must be auto-unlocked by the service, so it is functionally equivalent to a file on disk protected by filesystem permissions. Do not pretend otherwise. Mitigate by keeping the wallet drained to the operational float only, and by refilling from a cold wallet manually as needed.
- **Routing:** Jupiter for graduated tokens; the launchpad's own program for tokens still on the curve. **VERIFY** whether Jupiter routes curve-stage tokens before relying on it. Set sensible priority fees; consider Jito bundles for landing reliability.
- **Pre-trade safety checks** (addresses fomo's biggest complaint, failed sells): simulate a sell, check mint authority and freeze authority, look at creator history and holder concentration. Show the results in the trade panel and block on hard failures.
- Start with a tiny balance and test on small amounts.

### 4.8 Operational concerns

**Backfill policy.** When a token joins the watchlist mid-lifetime, backfill its trade history from a data API (Helius parsed transactions, Birdeye, or DexScreener) into `trades`, then rely on the live stream from that point. Do not attempt to replay from arbitrary historical slots via RPC — too slow and expensive. Backfill is best-effort; only watchlist tokens need history.

**Observability.** Every service exposes:
- `/healthz` — returns 200 if the process is alive and its dependencies (DB, stream) are reachable.
- Prometheus-style metrics on `/metrics`: parse failures per minute, stream reconnects, `LISTEN` queue depth, executor pre-check failures, alert fire rate. Alert on `parse_failure_rate > threshold` — a silent decoder break is the single most likely failure mode.
- Structured JSON logs to stdout (`docker logs` / systemd captures them). **Never log signing keys, seeds, or full private-key material.**

## 5. Build order

1. **Ingestor + TimescaleDB.** Stream launchpad events, store trades, and verify a sample of rows against a block explorer.
2. **Aggregates + dashboard.** Continuous aggregates, token list, token detail with volume and buy/sell.
3. **Graduation and bonding tracking**, then the **alert engine + Telegram**.
4. **Trade executor**, non-custodial-style, capped wallet, small limits.

Do not start phase 4 until phases 1 to 3 are stable and verified.

Optional fast start: prototype phase 1 with a data API (Birdeye, DexScreener, Bitquery or Helius enhanced APIs) to skip decoding, then move the hot path to the raw stream once the product proves out. Trade-off: cost, latency, and no raw events.

## 6. Repo layout (suggested)

```
/services
  /ingestor        # Python: stream subscriber + decoder
  /alerts          # Python: rule engine + Telegram delivery
  /api             # Python: REST + WebSocket (FastAPI)
  /executor        # Python: isolated trading service (phase 4)
/dashboard         # Next.js (separate toolchain)
/packages
  /decoder         # Python package: IDL-based decoders, isolated, with fixtures
  /shared          # Python package: types, event schema, config
/db                # SQL migrations, continuous aggregates
/fixtures          # captured real transactions for tests
/docs              # decisions.md (VERIFY-source-of-truth), architecture notes
docker-compose.yml # timescaledb, python services
pyproject.toml     # workspace root, uv-managed
.env.example
```

## 7. Conventions for Claude Code

- Prefer small, verifiable steps. After each phase, show how to check it works (e.g. a query comparing stored trades to an explorer).
- Never commit secrets. Provide `.env.example`; keep real keys out of the repo and out of logs.
- Config (RPC/stream URLs, program IDs, thresholds, caps) lives in environment or config files, not hardcoded.
- Write decoder tests against real transaction fixtures; add a fixture whenever a parse failure is found.
- Make the executor's limits enforceable in code and hard to bypass; do not add a flag that disables them.
- Prices, amounts and reserves are large or high-precision: use `NUMERIC`/BigInt, not floating point, for stored values.
- When a fact is marked **VERIFY**, look it up (docs, on-chain, provider) and record the source in a comment or in `docs/`.

## 8. Known risks and pitfalls

- **Decoder drift:** launchpads upgrade programs. Isolate decoders and monitor parse failures.
- **Data volume and cost:** stream and RPC costs can grow quickly on busy launchpads. Budget for it and consider filtering to watched tokens early.
- **Source disagreement:** prices and timestamps differ across sources. Pick one source of truth.
- **Reorgs and failed transactions:** only treat data as final at the chosen commitment level.
- **Memecoin risk:** most tokens fail or are scams; graduation is not safety. The dashboard should surface liquidity, holder concentration and the sell-simulation result.
- **Clone/phishing sites:** typosquats of crypto apps exist. Irrelevant to a personal tool, but never connect a wallet to unknown sites.
- **Legal:** this is a personal tool trading the user's own funds. Do not hold or move other people's funds or keys without legal advice; that can bring money-transmitter rules into play.

## 9. Open questions for the user

- Run locally, or on a VPS for always-on alerts?
- Which stream provider (Helius, Triton, QuickNode) and what budget?
- Track all new launchpad tokens, or only a watchlist plus tokens that pass a threshold (affects data volume)?
- Should Telegram be the only alert channel?
