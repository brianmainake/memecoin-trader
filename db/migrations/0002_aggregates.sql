-- 0002_aggregates.sql — continuous aggregates over trades for the dashboard.
-- Aggregates lag by their refresh interval; the alert engine must NOT read
-- from these (it uses in-memory rolling windows). See CLAUDE.md §4.3, §4.4.

CREATE MATERIALIZED VIEW trades_1m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket('1 minute'::interval, time)              AS bucket,
    mint,
    first(price_sol, time)                                AS open,
    max(price_sol)                                        AS high,
    min(price_sol)                                        AS low,
    last(price_sol, time)                                 AS close,
    sum(sol_lamports)                                     AS volume_sol_lamports,
    sum(token_base_units)                                 AS volume_token_base_units,
    count(*)                                              AS trade_count,
    count(*) FILTER (WHERE side = 'buy')                  AS buy_count,
    count(*) FILTER (WHERE side = 'sell')                 AS sell_count,
    sum(sol_lamports) FILTER (WHERE side = 'buy')         AS buy_sol_lamports,
    sum(sol_lamports) FILTER (WHERE side = 'sell')        AS sell_sol_lamports
FROM trades
GROUP BY bucket, mint
WITH NO DATA;

CREATE MATERIALIZED VIEW trades_5m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket('5 minutes'::interval, time)             AS bucket,
    mint,
    first(price_sol, time)                                AS open,
    max(price_sol)                                        AS high,
    min(price_sol)                                        AS low,
    last(price_sol, time)                                 AS close,
    sum(sol_lamports)                                     AS volume_sol_lamports,
    sum(token_base_units)                                 AS volume_token_base_units,
    count(*)                                              AS trade_count,
    count(*) FILTER (WHERE side = 'buy')                  AS buy_count,
    count(*) FILTER (WHERE side = 'sell')                 AS sell_count,
    sum(sol_lamports) FILTER (WHERE side = 'buy')         AS buy_sol_lamports,
    sum(sol_lamports) FILTER (WHERE side = 'sell')        AS sell_sol_lamports
FROM trades
GROUP BY bucket, mint
WITH NO DATA;

CREATE MATERIALIZED VIEW trades_1h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket('1 hour'::interval, time)                AS bucket,
    mint,
    first(price_sol, time)                                AS open,
    max(price_sol)                                        AS high,
    min(price_sol)                                        AS low,
    last(price_sol, time)                                 AS close,
    sum(sol_lamports)                                     AS volume_sol_lamports,
    sum(token_base_units)                                 AS volume_token_base_units,
    count(*)                                              AS trade_count,
    count(*) FILTER (WHERE side = 'buy')                  AS buy_count,
    count(*) FILTER (WHERE side = 'sell')                 AS sell_count,
    sum(sol_lamports) FILTER (WHERE side = 'buy')         AS buy_sol_lamports,
    sum(sol_lamports) FILTER (WHERE side = 'sell')        AS sell_sol_lamports
FROM trades
GROUP BY bucket, mint
WITH NO DATA;

CREATE MATERIALIZED VIEW trades_24h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket('1 day'::interval, time)                 AS bucket,
    mint,
    first(price_sol, time)                                AS open,
    max(price_sol)                                        AS high,
    min(price_sol)                                        AS low,
    last(price_sol, time)                                 AS close,
    sum(sol_lamports)                                     AS volume_sol_lamports,
    sum(token_base_units)                                 AS volume_token_base_units,
    count(*)                                              AS trade_count,
    count(*) FILTER (WHERE side = 'buy')                  AS buy_count,
    count(*) FILTER (WHERE side = 'sell')                 AS sell_count,
    sum(sol_lamports) FILTER (WHERE side = 'buy')         AS buy_sol_lamports,
    sum(sol_lamports) FILTER (WHERE side = 'sell')        AS sell_sol_lamports
FROM trades
GROUP BY bucket, mint
WITH NO DATA;

-- Refresh policies. end_offset keeps a small buffer to avoid partial buckets;
-- start_offset caps how far back each refresh will look.
SELECT add_continuous_aggregate_policy('trades_1m',
    start_offset      => INTERVAL '2 hours',
    end_offset        => INTERVAL '30 seconds',
    schedule_interval => INTERVAL '30 seconds');

SELECT add_continuous_aggregate_policy('trades_5m',
    start_offset      => INTERVAL '1 day',
    end_offset        => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '1 minute');

SELECT add_continuous_aggregate_policy('trades_1h',
    start_offset      => INTERVAL '7 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes');

SELECT add_continuous_aggregate_policy('trades_24h',
    start_offset      => INTERVAL '30 days',
    end_offset        => INTERVAL '1 day',
    schedule_interval => INTERVAL '30 minutes');

-- Read-side indexes on the underlying materialization hypertables. Timescale
-- names them _materialized_hypertable_<n>; the CAGG view queries route through
-- these. Adding indexes on (mint, bucket DESC) makes per-token candle queries
-- fast without needing to change the CAGG definition.
CREATE INDEX ON trades_1m  (mint, bucket DESC);
CREATE INDEX ON trades_5m  (mint, bucket DESC);
CREATE INDEX ON trades_1h  (mint, bucket DESC);
CREATE INDEX ON trades_24h (mint, bucket DESC);
