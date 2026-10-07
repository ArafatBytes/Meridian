-- ============================================================================
-- Meridian — DESTRUCTIVE RESET
-- ============================================================================
--
--   ⚠️  THIS DELETES ALL APPLICATION DATA. IT CANNOT BE UNDONE.
--
-- Only run this when you genuinely want to start the schema over. It drops
-- every Meridian table, the enum, the trigger function, the storage policies
-- and every file in the avatars bucket.
--
-- It does NOT delete auth.users. Your accounts survive. To remove those too,
-- use the Supabase dashboard (Authentication → Users) or the Admin API —
-- deleting from auth.users by hand here would cascade through tables that no
-- longer exist and is not worth the risk.
--
-- Usage: run this, then run SCHEMA.sql, then VERIFY.sql.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. Storage: policies, then objects, then the bucket
-- ---------------------------------------------------------------------------
drop policy if exists "avatars_insert_own_folder" on storage.objects;
drop policy if exists "avatars_update_own_folder" on storage.objects;
drop policy if exists "avatars_delete_own_folder" on storage.objects;
drop policy if exists "avatars_public_read"       on storage.objects;

delete from storage.objects where bucket_id = 'avatars';
delete from storage.buckets where id = 'avatars';


-- ---------------------------------------------------------------------------
-- 2. Tables
-- ---------------------------------------------------------------------------
-- CASCADE takes the policies, triggers, indexes and foreign keys with them.
drop table if exists public.user_locations     cascade;
drop table if exists public.sos_incidents      cascade;
drop table if exists public.sos_hot_words      cascade;
drop table if exists public.emergency_contacts cascade;
drop table if exists public.crime_reports      cascade;
drop table if exists public.users              cascade;
drop table if exists public.profiles           cascade;


-- ---------------------------------------------------------------------------
-- 3. Types and functions
-- ---------------------------------------------------------------------------
drop type     if exists public.crime_category cascade;
drop function if exists public.set_updated_at() cascade;


-- ---------------------------------------------------------------------------
-- 4. Leftovers from the pre-S01 migrations
-- ---------------------------------------------------------------------------
-- The old backend/migrations/*.sql files created these. Harmless if absent.
drop function if exists public.update_crime_reports_updated_at() cascade;
drop function if exists public.update_updated_at_column() cascade;
delete from storage.objects where bucket_id = 'profile-pictures';
delete from storage.buckets where id = 'profile-pictures';

drop policy if exists "Users can upload own profile picture" on storage.objects;
drop policy if exists "Users can update own profile picture" on storage.objects;
drop policy if exists "Users can delete own profile picture" on storage.objects;
drop policy if exists "Public can view profile pictures"     on storage.objects;


-- ---------------------------------------------------------------------------
-- 5. Reload PostgREST
-- ---------------------------------------------------------------------------
notify pgrst, 'reload schema';


-- ============================================================================
-- Schema is now empty. Run SCHEMA.sql next.
-- ============================================================================
