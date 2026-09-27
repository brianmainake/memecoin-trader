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
        |-----------------------------|
Redis streams (live events, hot state)   TimescaleDB (trades, candles, rules)
        |                                |
Alert engine ----> Telegram          API server (REST + WebSocket) ----> Dashboard
                                         |
                                   Trade executor (isolated, capped hot wallet)
                                         |
                                   Swap routing (Jupiter / launchpad program)
```

Colour logic from the design diagram: everything except the executor is **read-only** and safe to build first. The executor **touches money**: build it last and keep it isolated.

### Design decisions
- **Single machine**, Docker Compose. Laptop or a small VPS (VPS preferred for alerts while the laptop is closed).
- **One database.** TimescaleDB (Postgres + time-series extension) holds trades, candles, watchlists and alert rules. Continuous aggregates produce 1m/5m/1h volume and buy/sell counts. No separate analytics store.
- **Redis** only for live fan-out between processes and hot state. Nothing durable lives only in Redis.
- **Provider stream, not a self-run node.** Use a gRPC/Geyser stream, not RPC polling (too slow). **VERIFY** current free-tier limits and pricing.
- **Telegram bot** for alerts (simplest for personal use).
- **Solana only, one launchpad first** (pump.fun and the pool it graduates into). Each additional venue multiplies decoder work.

### Language and stack
- **Decision pending: confirm with the user at the start.** Default to **TypeScript** everywhere (ingestor, alert engine, API, executor, Next.js dashboard) so there is one language and one toolchain. Python is an acceptable alternative for the ingestor and analytics if the user prefers.
- Dashboard: Next.js + TradingView `lightweight-charts`.
- Tests: use real captured transactions as fixtures for the decoder.

## 4. Components

### 4.1 Ingestor
- Subscribes to the launchpad program and to the pools tokens migrate into (and to curve account updates for watched tokens).
- Decodes with the program IDLs into a normalized event stream. Event types: `token_created`, `buy`, `sell`, `curve_complete`, `graduated` (migration to pool), plus pool swaps after graduation.
- Dedupes by transaction signature. Ignores failed transactions. Treats data as final only at the chosen commitment level (note reorg risk at lower levels).
- Reconnects with backoff and replays from the last seen slot where the provider allows.
- Decoder lives in **its own isolated module**. Launchpads upgrade programs and decoders break. Log every transaction that cannot be parsed and alert on parse-failure rate so a silent break is visible.
- Writes each event to Redis streams (live path) and TimescaleDB (history).

### 4.2 Normalized trade schema (the key table, get this right)
One row per trade: signature, slot, block time, wallet, token mint, side (buy/sell), SOL amount, token amount, price, venue (curve or pool id). Everything else is derived from this.

Sketch (adjust as needed):

```sql
CREATE TABLE tokens (
  mint            TEXT PRIMARY KEY,
  symbol          TEXT,
  name            TEXT,
  creator         TEXT,
  created_at      TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'bonding',  -- bonding | graduated
  graduated_at    TIMESTAMPTZ,
  pool_address    TEXT,
  curve_address   TEXT
);

CREATE TABLE trades (
  time         TIMESTAMPTZ NOT NULL,
  signature    TEXT NOT NULL,
  slot         BIGINT NOT NULL,
  mint         TEXT NOT NULL,
  wallet       TEXT NOT NULL,
  side         TEXT NOT NULL,           -- buy | sell
  sol_amount   NUMERIC NOT NULL,
  token_amount NUMERIC NOT NULL,
  price_sol    NUMERIC NOT NULL,
  venue        TEXT NOT NULL,           -- curve | pool
  PRIMARY KEY (signature, mint, wallet, side, time)
);
SELECT create_hypertable('trades', 'time');

CREATE TABLE curve_snapshots (
  time            TIMESTAMPTZ NOT NULL,
  mint            TEXT NOT NULL,
  real_sol_reserves  NUMERIC,
  real_token_reserves NUMERIC,
  progress_pct    NUMERIC
);
SELECT create_hypertable('curve_snapshots', 'time');

CREATE TABLE watchlist (mint TEXT PRIMARY KEY, added_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE tracked_wallets (wallet TEXT PRIMARY KEY, label TEXT);
CREATE TABLE alert_rules (
  id SERIAL PRIMARY KEY, type TEXT NOT NULL, params JSONB NOT NULL,
  enabled BOOLEAN DEFAULT true, cooldown_seconds INT DEFAULT 300
);
CREATE TABLE alert_log (
  id BIGSERIAL PRIMARY KEY, rule_id INT, mint TEXT, fired_at TIMESTAMPTZ DEFAULT now(), payload JSONB
);
```

Continuous aggregates over `trades` for 1m, 5m, 1h and 24h: OHLC price, total volume, buy count, sell count, buy volume, sell volume.

### 4.3 Derived metrics for the dashboard
- Volume, buy/sell counts and buy/sell ratio over 1m, 5m, 1h, 24h windows.
- OHLCV candles.
- **Bonding progress:** compute from the curve account's reserves (not by counting trades) and compare against the curve's completion target. **VERIFY** the account layout and target.
- **Graduation:** detect the migration event, flip `tokens.status`, record the pool address, and start indexing the new pool.
- **Holders and top-holder concentration:** hardest part (needs token-account snapshots). Use a provider API at first (e.g. Helius or Birdeye). Do not build it yourself early.
- USD values: use one consistent SOL/USD price source and record which one.

### 4.4 Alert engine
- Consumes the Redis stream and evaluates rules **in memory as events arrive** (not on a schedule). Rules and cooldown state are loaded from Postgres.
- Starter rule types:
  - `graduated`: a watched or any token graduates
  - `bonding_progress`: crosses a threshold (e.g. 80%)
  - `volume_spike`: volume over a window exceeds N times its recent baseline
  - `large_trade`: single buy or sell above a size
  - `wallet_trade`: a tracked wallet trades
- **Per-token cooldown and dedupe from day one**, or busy tokens will spam.
- Delivery: Telegram bot. Keep a delivery interface so other channels can be added.
- Log every fired alert to `alert_log`.

### 4.5 API server
- REST for history (tokens, candles, trades, watchlist, rules).
- WebSocket for live token stats and alerts.
- Talks to TimescaleDB and Redis. Calls the executor over a local internal interface for trades.

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
- **Routing:** Jupiter for graduated tokens; the launchpad's own program for tokens still on the curve. **VERIFY** whether Jupiter routes curve-stage tokens before relying on it. Set sensible priority fees; consider Jito bundles for landing reliability.
- **Pre-trade safety checks** (addresses fomo's biggest complaint, failed sells): simulate a sell, check mint authority and freeze authority, look at creator history and holder concentration. Show the results in the trade panel and block on hard failures.
- Start with a tiny balance and test on small amounts.

## 5. Build order

1. **Ingestor + TimescaleDB.** Stream launchpad events, store trades, and verify a sample of rows against a block explorer.
2. **Aggregates + dashboard.** Continuous aggregates, token list, token detail with volume and buy/sell.
3. **Graduation and bonding tracking**, then the **alert engine + Telegram**.
4. **Trade executor**, non-custodial-style, capped wallet, small limits.

Do not start phase 4 until phases 1 to 3 are stable and verified.

Optional fast start: prototype phase 1 with a data API (Birdeye, DexScreener, Bitquery or Helius enhanced APIs) to skip decoding, then move the hot path to the raw stream once the product proves out. Trade-off: cost, latency, and no raw events.

## 6. Repo layout (suggested)

```
/apps
  /ingestor        # stream subscriber + decoder
  /alerts          # rule engine + Telegram delivery
  /api             # REST + WebSocket
  /executor        # isolated trading service (phase 4)
  /dashboard       # Next.js
/packages
  /decoder         # IDL-based decoders, isolated, with fixtures
  /shared          # types, event schema, config
/db                # migrations, continuous aggregates
/fixtures          # captured real transactions for tests
docker-compose.yml # timescaledb, redis, services
.env.example
```

## 7. Conventions for Claude Code

- Ask before choosing between TypeScript and Python if the user hasn't said (see section 3).
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

- TypeScript or Python?
- Run locally, or on a VPS for always-on alerts?
- Which stream provider (Helius, Triton, QuickNode) and what budget?
- Track all new launchpad tokens, or only a watchlist plus tokens that pass a threshold (affects data volume)?
- Should Telegram be the only alert channel?
