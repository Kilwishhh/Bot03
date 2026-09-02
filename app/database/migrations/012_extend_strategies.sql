-- Migration 012: Extend strategies table for full strategy builder
-- Adds columns that cannot be stored in JSON-only config
-- Preserves all existing data

-- universe_type: how to pick symbols
ALTER TABLE strategies ADD COLUMN universe_type TEXT NOT NULL DEFAULT 'all_binance_futures'
    CHECK (universe_type IN ('all_binance_futures', 'top_n_futures', 'custom_watchlist'));

-- universe_config: JSON for top_n count or custom symbol list
ALTER TABLE strategies ADD COLUMN universe_config TEXT NOT NULL DEFAULT '{}';

-- confirmation_timeframes: JSON list of extra timeframes
ALTER TABLE strategies ADD COLUMN confirmation_timeframes TEXT NOT NULL DEFAULT '[]';

-- indicators_config: JSON list of full indicator definitions
ALTER TABLE strategies ADD COLUMN indicators_config TEXT NOT NULL DEFAULT '[]';

-- conditions_config: JSON for entry/exit condition groups
ALTER TABLE strategies ADD COLUMN conditions_config TEXT NOT NULL DEFAULT '{}';

-- filters_config: JSON for market filters (min_volume, etc.)
ALTER TABLE strategies ADD COLUMN filters_config TEXT NOT NULL DEFAULT '{}';

-- confidence_config: JSON for confidence settings
ALTER TABLE strategies ADD COLUMN confidence_config TEXT NOT NULL DEFAULT '{}';

-- notes: user notes
ALTER TABLE strategies ADD COLUMN notes TEXT;

-- enabled_at: when strategy was last enabled (NULL = never)
ALTER TABLE strategies ADD COLUMN enabled_at TEXT;

-- disabled_at: when strategy was last disabled (NULL = never)
ALTER TABLE strategies ADD COLUMN disabled_at TEXT;

-- Also extend signals table to track strategy_id properly (if not already)
-- Check and add if missing:
-- (The existing signals table stores 'strategy' as text, we'll use strategy_id for FK lookups)

-- Ensure mode column exists on signals (for paper/testnet/live separation)
-- This is handled by migration 002 already

-- Ensure mode column exists on trades (for paper/testnet/live separation)
-- This is handled by migration 002 already
