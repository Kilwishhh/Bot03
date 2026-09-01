-- P0-01 (regression fix): scope the dev-signal cooldown check by strategy.
-- The previous cooldown query (`SELECT symbol FROM positions` without a
-- strategy filter) caused open positions on strategy A to block signal
-- generation on strategy B. Add `strategy_id` to positions so the query
-- can be scoped properly.
--
-- Existing rows (pre-migration) have NULL strategy_id and remain visible
-- to the unscoped dev-signal cooldown path; new code must filter by
-- strategy_id explicitly. Legacy rows are typically cleaned up at restart
-- via the existing emergency_pauses / lifecycle cleanup.

ALTER TABLE positions ADD COLUMN strategy_id TEXT;
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_id);
