-- Force Supabase Schema Reload
-- Run this in Supabase SQL Editor to refresh the schema cache

-- Method 1: Create and drop a dummy table to trigger schema reload
CREATE TABLE IF NOT EXISTS _schema_reload_trigger (id int);
DROP TABLE IF EXISTS _schema_reload_trigger;

-- Method 2: Grant permissions again to ensure PostgREST sees the column
GRANT ALL ON emergency_contacts TO anon, authenticated;

-- Method 3: Verify the column exists
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'emergency_contacts' 
ORDER BY ordinal_position;

-- Expected output should include:
-- email | character varying | NO
