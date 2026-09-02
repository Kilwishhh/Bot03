-- ERMIS Migration 001: Core multi-user, strategies, signals, automation, audit
-- Idempotent: each CREATE uses IF NOT EXISTS. Safe to re-run.

-- =========================================================================
-- 1. Users & sessions
-- =========================================================================
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    role            TEXT NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user','admin','system')),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','suspended','deleted')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

CREATE TABLE IF NOT EXISTS user_sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_used_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);

-- =========================================================================
-- 2. Strategies + lifecycle + versions + backtests
-- =========================================================================
CREATE TABLE IF NOT EXISTS strategies (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    version         INTEGER NOT NULL DEFAULT 1,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft'
                    CHECK (lifecycle_state IN (
                        'draft','backtest','paper','testnet',
                        'live_eligible','live','paused','stopped')),
    execution_mode  TEXT NOT NULL DEFAULT 'paper'
                    CHECK (execution_mode IN ('paper','testnet','live')),
    execution_venue TEXT NOT NULL DEFAULT 'binance'
                    CHECK (execution_venue IN ('binance','hyperliquid','walletconnect')),
    market          TEXT NOT NULL,
    timeframe       TEXT NOT NULL DEFAULT '15m'
                    CHECK (timeframe IN ('1m','3m','5m','7m','10m','15m','20m','30m','45m','90m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M')),
    entry_config    TEXT NOT NULL DEFAULT '{}',
    exit_config     TEXT NOT NULL DEFAULT '{}',
    risk_config     TEXT NOT NULL DEFAULT '{}',
    template_name   TEXT,
    template_params TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategies_user    ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_state   ON strategies(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_strategies_market  ON strategies(market);

CREATE TABLE IF NOT EXISTS strategy_lifecycle_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id     TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    from_state      TEXT,
    to_state        TEXT NOT NULL,
    actor_user_id   TEXT REFERENCES users(id) ON DELETE SET NULL,
    actor_role      TEXT NOT NULL CHECK (actor_role IN ('user','admin','system')),
    reason          TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_strategy ON strategy_lifecycle_events(strategy_id);

CREATE TABLE IF NOT EXISTS strategy_versions (
    id              TEXT PRIMARY KEY,
    strategy_id     TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    config_snapshot TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE (strategy_id, version)
);

CREATE TABLE IF NOT EXISTS backtests (
    id              TEXT PRIMARY KEY,
    strategy_id     TEXT NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','completed','failed')),
    result_summary  TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    error_message   TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtests_user     ON backtests(user_id);

-- =========================================================================
-- 3. Connections (encrypted secrets at rest)
-- =========================================================================
CREATE TABLE IF NOT EXISTS exchange_connections (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    venue           TEXT NOT NULL
                    CHECK (venue IN ('binance','hyperliquid','walletconnect')),
    label           TEXT,
    api_key_enc     BLOB NOT NULL,
    api_secret_enc  BLOB,
    wallet_address  TEXT,
    permissions     TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'connected'
                    CHECK (status IN ('connected','disconnected','error')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connections_user_venue ON exchange_connections(user_id, venue);

-- =========================================================================
-- 4. Automation rules
-- =========================================================================
CREATE TABLE IF NOT EXISTS automation_rules (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id     TEXT REFERENCES strategies(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    trigger         TEXT NOT NULL
                    CHECK (trigger IN (
                        'signal_generated','tp1_hit','tp2_hit',
                        'sl_hit','stop_moved','position_closed')),
    conditions      TEXT NOT NULL DEFAULT '[]',
    actions         TEXT NOT NULL DEFAULT '[]',
    enabled         INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rules_user     ON automation_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_rules_strategy ON automation_rules(strategy_id);
CREATE INDEX IF NOT EXISTS idx_rules_trigger  ON automation_rules(trigger);

CREATE TABLE IF NOT EXISTS automation_events (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL REFERENCES automation_rules(id) ON DELETE CASCADE,
    signal_id       TEXT,
    followup_id     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','completed','failed','retrying')),
    result          TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    dedup_key       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    UNIQUE (rule_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_auto_events_status ON automation_events(status);

-- =========================================================================
-- 5. Publishing configs + publication log
-- =========================================================================
CREATE TABLE IF NOT EXISTS publishing_configs (
    user_id             TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    telegram_token_enc  BLOB,
    telegram_chat_id    TEXT,
    telegram_enabled    INTEGER NOT NULL DEFAULT 0 CHECK (telegram_enabled IN (0,1)),
    square_api_key_enc  BLOB,
    square_endpoint     TEXT,
    square_daily_limit  INTEGER NOT NULL DEFAULT 95,
    square_limit_behavior TEXT NOT NULL DEFAULT 'queue'
                          CHECK (square_limit_behavior IN ('stop_square','telegram_only','queue')),
    square_enabled      INTEGER NOT NULL DEFAULT 0 CHECK (square_enabled IN (0,1)),
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_id       TEXT,
    channel         TEXT NOT NULL CHECK (channel IN ('telegram','binance_square')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','sent','failed','rate_limited','duplicate')),
    posted_at       TEXT,
    error_message   TEXT,
    dedup_key       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE (user_id, channel, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_publications_user ON publications(user_id, created_at DESC);

-- =========================================================================
-- 6. Emergency pauses (3 scopes)
-- =========================================================================
CREATE TABLE IF NOT EXISTS emergency_pauses (
    id              TEXT PRIMARY KEY,
    scope           TEXT NOT NULL
                    CHECK (scope IN ('strategy','user','integration','platform')),
    scope_target    TEXT,
    actor_user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    actor_role      TEXT NOT NULL CHECK (actor_role IN ('user','admin','system')),
    reason          TEXT NOT NULL,
    close_positions INTEGER NOT NULL DEFAULT 0 CHECK (close_positions IN (0,1)),
    created_at      TEXT NOT NULL,
    expires_at      TEXT,
    resumed_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_pauses_scope ON emergency_pauses(scope, scope_target);

-- =========================================================================
-- 7. Audit log (structured table; existing JSONL file mirror)
-- =========================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id   TEXT REFERENCES users(id) ON DELETE SET NULL,
    actor_role      TEXT NOT NULL,
    action          TEXT NOT NULL,
    target_type     TEXT,
    target_id       TEXT,
    detail          TEXT,
    result          TEXT NOT NULL CHECK (result IN ('ok','rejected','error')),
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_actor   ON audit_log(actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action  ON audit_log(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_target  ON audit_log(target_type, target_id);

-- =========================================================================
-- 8. Migration tracking
-- =========================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL
);
