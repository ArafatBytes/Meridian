# Supabase Schema Cache Issue - SOLUTION

## Problem
Error: `Could not find the 'email' column of 'emergency_contacts' in the schema cache`

## Root Cause
The `email` column exists in the PostgreSQL database, but Supabase's PostgREST API layer hasn't refreshed its schema cache yet.

## ✅ VERIFIED
The column exists in the database:
```
 column_name  |     data_type     | is_nullable 
--------------+-------------------+-------------
 id           | character varying | NO
 user_id      | character varying | NO
 name         | character varying | NO
 phone        | character varying | NO
 relationship | character varying | YES
 email        | character varying | NO  ← EXISTS!
```

## Solutions (Try in Order)

### 1. Supabase Dashboard - Restart PostgREST (FASTEST)

1. Go to: https://supabase.com/dashboard/project/lpfsoinrwkapkxwprhpc
2. Navigate to: **Settings** → **Database**
3. Scroll down to find **"Connection pooling"** or **"PostgREST"** section
4. Look for a **"Restart"** or **"Reload Schema"** button
5. Click it

**OR**

1. Go to: **Database** → **Roles**
2. Click on any role (e.g., `postgres`)
3. This sometimes triggers a schema refresh

### 2. SQL Editor Method

1. Go to: https://supabase.com/dashboard/project/lpfsoinrwkapkxwprhpc/sql
2. Create a new query
3. Paste and run:

```sql
-- Force schema reload by modifying and reverting a permission
REVOKE ALL ON emergency_contacts FROM service_role;
GRANT ALL ON emergency_contacts TO service_role;

-- Verify column exists
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'emergency_contacts' 
ORDER BY ordinal_position;
```

### 3. Wait for Auto-Refresh (5-10 minutes)

Supabase automatically refreshes the schema cache every 5-10 minutes. Just wait and try again.

### 4. Create a Dummy Column (Nuclear Option)

If nothing else works:

```sql
-- Add a dummy column to force cache refresh
ALTER TABLE emergency_contacts ADD COLUMN IF NOT EXISTS _cache_buster INT DEFAULT 0;
ALTER TABLE emergency_contacts DROP COLUMN IF EXISTS _cache_buster;
```

## Verification

After trying any solution, test in your app:
1. Open the Emergency Contacts screen
2. Try to add a contact with name, phone, and email
3. It should work without errors

## Prevention

For future schema changes on Supabase:
1. Always use the Supabase Dashboard SQL Editor for migrations
2. After running migrations, manually restart PostgREST
3. Or wait 10 minutes before testing

## Current Status

- ✅ Database column added successfully
- ✅ Column is NOT NULL as required
- ✅ Index created for performance
- ⏳ Waiting for Supabase PostgREST cache refresh

## Need Help?

If the error persists after 15 minutes:
1. Check Supabase status: https://status.supabase.com/
2. Contact Supabase support
3. Or temporarily switch to direct PostgreSQL connection (bypass PostgREST)
