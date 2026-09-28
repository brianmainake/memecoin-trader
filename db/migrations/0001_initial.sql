-- 0001_initial.sql — initial schema for personal Solana memecoin tracker.
-- See CLAUDE.md §4.2 for design rationale.

CREATE EXTENSION IF NOT EXISTS timescaledb;

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

-- 'time' is included in the PK because Timescale requires the partitioning
-- column to appear in every unique constraint. Uniqueness in practice is
-- still (signature, event_index).
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
  PRIMARY KEY (signature, event_index, time)
);
SELECT create_hypertable('trades', 'time');
CREATE INDEX trades_mint_time_idx ON trades (mint, time DESC);
CREATE INDEX trades_wallet_time_idx ON trades (wallet, time DESC);

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
