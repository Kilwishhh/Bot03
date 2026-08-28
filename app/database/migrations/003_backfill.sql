-- ERMIS Migration 003: Backfill + indexes
-- Idempotent: backfill is safe to re-run; only updates NULL rows.

-- Backfill id (uuid-like) for any legacy signals
UPDATE signals SET id = lower(hex(randomblob(4))) || '-' ||
                        lower(hex(randomblob(2))) || '-4' ||
                        substr(lower(hex(randomblob(2))), 2) || '-' ||
                        substr('89ab', abs(random()) % 4 + 1, 1) ||
                        substr(lower(hex(randomblob(2))), 2) || '-' ||
                        lower(hex(randomblob(6)))
 WHERE id IS NULL;

UPDATE signals SET user_id = 'system'
 WHERE user_id IS NULL;

UPDATE signals SET created_at = timestamp
 WHERE created_at IS NULL AND timestamp IS NOT NULL;

UPDATE signals SET updated_at = COALESCE(created_at, timestamp, '')
 WHERE updated_at IS NULL;

-- Seed a "system" user so the backfilled signals reference a real row.
INSERT OR IGNORE INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at)
VALUES (
    'system', 'system@ermis.local',
    '!disabled', 'System', 'system', 'active',
    '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
);

-- Helpful compound index
CREATE INDEX IF NOT EXISTS idx_signals_user_created ON signals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy_created ON signals(strategy_id, created_at DESC);
