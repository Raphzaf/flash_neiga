-- Migration: Add explanation column to traffic_signs table
-- Date: 2026-01-07

-- Add explanation column to traffic_signs table
ALTER TABLE traffic_signs ADD COLUMN IF NOT EXISTS explanation TEXT;

-- Optional: Add an index if we plan to search by explanation
-- CREATE INDEX IF NOT EXISTS idx_traffic_signs_explanation ON traffic_signs(explanation);
