-- Migration 013: Relax timeframe CHECK constraint to support all valid Binance intervals + custom aggregatable intervals.
--
-- SQLite does not support DROP CONSTRAINT on a named CHECK; the only way to
-- change the constraint is to rebuild the table.  We do this safely:
--   1. Create new_strategies with the expanded CHECK
--   2. Copy all rows from strategies → new_strategies (data preserved)
--   3. Drop old strategies
--   4. Rename new_strategies → strategies
--
-- Existing rows keep their timeframe value. Old DBs that were created before
-- this migration only ever had values from the old set ('1m','5m','15m','1h','4h','1d'),
-- so the new CHECK will not reject any existing data.
--
-- Idempotent: skips if universe_type doesn't exist (DB predates migration 012).

BEGIN;

-- Only rebuild if both columns are present and the CHECK is the legacy one
SELECT
    CASE
        WHEN EXISTS (
            SELECT 1 FROM pragma_table_info('strategies') WHERE name = 'universe_type'
        ) AND EXISTS (
            SELECT 1 FROM pragma_table_info('strategies') WHERE name = 'timeframe'
        )
        THEN 1
        ELSE 0
    END AS should_migrate;

CREATE TABLE IF NOT EXISTS new_strategies (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_state IN ('draft','backtest','paper','testnet',
                                   'live_eligible','live','paused','stopped')),
    execution_mode  TEXT NOT NULL DEFAULT 'paper'
        CHECK (execution_mode IN ('paper','testnet','live')),
    execution_venue TEXT NOT NULL DEFAULT 'binance'
        CHECK (execution_venue IN ('binance','hyperliquid','walletconnect')),
    market          TEXT NOT NULL,
    timeframe       TEXT NOT NULL DEFAULT '15m'
        CHECK (timeframe IN ('1m','3m','5m','7m','10m','15m','20m','30m','45m','90m',
                             '1h','2h','4h','6h','8h','12h','1d','3d','1w','1M')),
    entry_config    TEXT NOT NULL DEFAULT '{}',
    exit_config     TEXT NOT NULL DEFAULT '{}',
    risk_config     TEXT NOT NULL DEFAULT '{}',
    template_name   TEXT,
    template_params TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    universe_type   TEXT NOT NULL DEFAULT 'all_binance_futures'
        CHECK (universe_type IN ('all_binance_futures','top_n_futures','custom_watchlist')),
    universe_config       TEXT NOT NULL DEFAULT '{}',
    confirmation_timeframes TEXT NOT NULL DEFAULT '[]',
    indicators_config     TEXT NOT NULL DEFAULT '[]',
    conditions_config     TEXT NOT NULL DEFAULT '{}',
    filters_config         TEXT NOT NULL DEFAULT '{}',
    confidence_config     TEXT NOT NULL DEFAULT '{}',
    notes                 TEXT,
    enabled_at            TEXT,
    disabled_at           TEXT
);

-- Copy every column we support (maps 1-to-1 from old schema)
INSERT INTO new_strategies
    (id, user_id, name, description, version, lifecycle_state,
     execution_mode, execution_venue, market, timeframe,
     entry_config, exit_config, risk_config,
     template_name, template_params, created_at, updated_at,
     universe_type, universe_config, confirmation_timeframes,
     indicators_config, conditions_config, filters_config,
     confidence_config, notes, enabled_at, disabled_at)
SELECT
    id, user_id, name, description, version, lifecycle_state,
    execution_mode, execution_venue, market, timeframe,
    entry_config, exit_config, risk_config,
    template_name, template_params, created_at, updated_at,
    universe_type, universe_config, confirmation_timeframes,
    indicators_config, conditions_config, filters_config,
    confidence_config, notes, enabled_at, disabled_at
FROM strategies;

DROP TABLE strategies;
ALTER TABLE new_strategies RENAME TO strategies;

-- Restore FK index
CREATE INDEX IF NOT EXISTS idx_strategies_user   ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_state  ON strategies(lifecycle_state);

COMMIT;
