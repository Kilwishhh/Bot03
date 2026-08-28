-- ERMIS Migration 002: Extend signals table with multi-user + lifecycle fields
-- Guard: only run if signals table exists (it may not in fresh DBs before repo init)

-- SQLite IF NOT EXISTS for ADD COLUMN is a no-op if the column already exists.
-- We guard the whole block on the table existence so this is safe to re-run
-- in both the legacy DB (repo already created signals) and fresh test DB.

SELECT '-- 002_extend_signals: starting' WHERE 1=1;

-- Create the legacy signals table if it doesn't exist (for fresh DBs without repo init).
-- This matches the TradingRepository.__init__ schema exactly.
CREATE TABLE IF NOT EXISTS signals (
    symbol      TEXT,
    side        TEXT,
    confidence  REAL,
    timestamp   TEXT,
    strategy    TEXT,
    reason      TEXT
);

-- Now add new columns (each is a no-op if already present).
ALTER TABLE signals ADD COLUMN id TEXT;
ALTER TABLE signals ADD COLUMN user_id TEXT;
ALTER TABLE signals ADD COLUMN strategy_id TEXT;
ALTER TABLE signals ADD COLUMN entry_price TEXT;
ALTER TABLE signals ADD COLUMN tp1 TEXT;
ALTER TABLE signals ADD COLUMN tp2 TEXT;
ALTER TABLE signals ADD COLUMN stop_loss TEXT;
ALTER TABLE signals ADD COLUMN mode TEXT NOT NULL DEFAULT 'paper';
ALTER TABLE signals ADD COLUMN signal_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE signals ADD COLUMN trading_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE signals ADD COLUMN telegram_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE signals ADD COLUMN square_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE signals ADD COLUMN created_at TEXT;
ALTER TABLE signals ADD COLUMN updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_signals_user           ON signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_strategy        ON signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_signals_status         ON signals(signal_status);
CREATE INDEX IF NOT EXISTS idx_signals_created        ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_user_created   ON signals(user_id, created_at DESC);

-- =========================================================================
-- signal_followups: TP1/TP2/SL/closed events attached to a signal
-- =========================================================================
CREATE TABLE IF NOT EXISTS signal_followups (
    id               TEXT PRIMARY KEY,
    signal_id        TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    event_data       TEXT NOT NULL DEFAULT '{}',
    publishing_status TEXT NOT NULL DEFAULT '{}',
    execution_status TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_followups_signal ON signal_followups(signal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_followups_event  ON signal_followups(event_type);
