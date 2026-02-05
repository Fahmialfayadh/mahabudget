"""
Migration: Add period tracking to savings_goals

Run this SQL in your Supabase SQL editor to add period support:
"""

ALTER TABLE savings_goals 
ADD COLUMN IF NOT EXISTS period_type VARCHAR(20) DEFAULT 'this_month',
ADD COLUMN IF NOT EXISTS period_start TIMESTAMP,
ADD COLUMN IF NOT EXISTS period_end TIMESTAMP;

-- Update existing records to have default period type
UPDATE savings_goals 
SET period_type = 'this_month' 
WHERE period_type IS NULL;

-- Add a check constraint for period_type values
ALTER TABLE savings_goals 
ADD CONSTRAINT period_type_check 
CHECK (period_type IN ('this_month', 'this_week', 'custom'));
