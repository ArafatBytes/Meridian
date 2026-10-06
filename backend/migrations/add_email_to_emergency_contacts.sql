-- Migration: Add email column to emergency_contacts table
-- This migration adds the email field to store emergency contact email addresses

-- Add email column (nullable first to allow existing data)
ALTER TABLE emergency_contacts 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Update existing records with a placeholder email (optional - you can skip this if you want to manually update)
-- UPDATE emergency_contacts SET email = 'update-required@example.com' WHERE email IS NULL;

-- Make email NOT NULL after updating existing records (uncomment when ready)
-- ALTER TABLE emergency_contacts ALTER COLUMN email SET NOT NULL;

-- Add index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_emergency_contacts_email ON emergency_contacts(email);

-- Refresh the schema cache (for Supabase/PostgREST)
NOTIFY pgrst, 'reload schema';
