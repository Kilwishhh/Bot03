-- Preserve the time a position was opened for the Positions age display.
ALTER TABLE positions ADD COLUMN opened_at TEXT;
UPDATE positions
SET opened_at = COALESCE(updated_at, datetime('now'))
WHERE opened_at IS NULL;
