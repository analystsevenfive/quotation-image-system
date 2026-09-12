-- Migration 005: Convert sync_logs and products timestamps to Thai format (DD/MM/YYYY HH:MI)
-- Formats time as Bangkok local time (UTC+7) with hours and minutes

-- 1. Add duration column to sync_logs
ALTER TABLE sync_logs ADD COLUMN IF NOT EXISTS duration text;

-- 2. Convert sync_logs started_at and completed_at to text formatted as DD/MM/YYYY HH24:MI
DROP INDEX IF EXISTS sync_logs_started_at_idx;

ALTER TABLE sync_logs 
  ALTER COLUMN started_at TYPE text 
  USING to_char(timezone('Asia/Bangkok', started_at), 'DD/MM/YYYY HH24:MI');

ALTER TABLE sync_logs 
  ALTER COLUMN completed_at TYPE text 
  USING to_char(timezone('Asia/Bangkok', completed_at), 'DD/MM/YYYY HH24:MI');

-- 3. Populate duration for existing rows
UPDATE sync_logs SET duration = '5 นาที 7 วินาที' WHERE id = 1 AND duration IS NULL;
UPDATE sync_logs SET duration = '3 นาที 25 วินาที' WHERE id = 2 AND duration IS NULL;

-- 4. Convert products last_sync_at to text formatted as DD/MM/YYYY HH24:MI
ALTER TABLE products 
  ALTER COLUMN last_sync_at TYPE text 
  USING to_char(timezone('Asia/Bangkok', last_sync_at), 'DD/MM/YYYY HH24:MI');
