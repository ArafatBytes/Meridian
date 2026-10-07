-- ============================================================================
-- Meridian — schema verification
-- ============================================================================
-- Run after SCHEMA.sql. Every check should report 'OK'.
-- Any 'MISSING' or 'FAIL' row means the app will break at runtime.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Tables
-- ---------------------------------------------------------------------------
select
    t.expected as table_name,
    case when c.table_name is null then '❌ MISSING' else '✅ OK' end as status
from (values
    ('profiles'),
    ('crime_reports'),
    ('emergency_contacts'),
    ('sos_hot_words'),
    ('users'),
    ('sos_incidents'),
    ('user_locations')
) as t(expected)
left join information_schema.tables c
       on c.table_schema = 'public'
      and c.table_name   = t.expected
order by t.expected;


-- ---------------------------------------------------------------------------
-- 2. Row Level Security is ON everywhere
-- ---------------------------------------------------------------------------
-- An RLS-off table with grants is an open door. This must be all OK.
select
    tablename,
    case when rowsecurity then '✅ OK' else '❌ FAIL — RLS IS OFF' end as rls_status
from pg_tables
where schemaname = 'public'
  and tablename in (
      'profiles', 'crime_reports', 'emergency_contacts', 'sos_hot_words',
      'users', 'sos_incidents', 'user_locations'
  )
order by tablename;


-- ---------------------------------------------------------------------------
-- 3. Policy counts
-- ---------------------------------------------------------------------------
-- Expected: profiles 3, crime_reports 4, emergency_contacts 4,
--           sos_hot_words 3, and ZERO for the three backend-only tables.
select
    tablename,
    count(*) as policies,
    case tablename
        when 'profiles'           then case when count(*) = 3 then '✅ OK' else '❌ expected 3' end
        when 'crime_reports'      then case when count(*) = 4 then '✅ OK' else '❌ expected 4' end
        when 'emergency_contacts' then case when count(*) = 4 then '✅ OK' else '❌ expected 4' end
        when 'sos_hot_words'      then case when count(*) = 3 then '✅ OK' else '❌ expected 3' end
        else '⚠️  unexpected table'
    end as status
from pg_policies
where schemaname = 'public'
group by tablename
order by tablename;

-- Backend-only tables must have no policies at all.
select
    'backend-only tables have no policies' as check_name,
    case when count(*) = 0 then '✅ OK'
         else '❌ FAIL — ' || count(*) || ' policy/policies found' end as status
from pg_policies
where schemaname = 'public'
  and tablename in ('users', 'sos_incidents', 'user_locations');


-- ---------------------------------------------------------------------------
-- 4. crime_category enum values
-- ---------------------------------------------------------------------------
-- Must be lowercase and must match AddReportScreen's CRIME_CATEGORIES ids.
select
    'crime_category values' as check_name,
    string_agg(e.enumlabel, ', ' order by e.enumsortorder) as values,
    case when count(*) = 8 then '✅ OK' else '❌ expected 8' end as status
from pg_type t
join pg_enum e on e.enumtypid = t.oid
where t.typname = 'crime_category'
group by t.typname;


-- ---------------------------------------------------------------------------
-- 5. Columns the app actually sends
-- ---------------------------------------------------------------------------
-- A missing column here is the exact failure mode that produced
-- SUPABASE_SCHEMA_CACHE_FIX.md ("could not find the 'email' column").
select
    x.tbl || '.' || x.col as required_column,
    case when c.column_name is null then '❌ MISSING' else '✅ OK' end as status
from (values
    ('profiles', 'id'), ('profiles', 'email'), ('profiles', 'name'),
    ('profiles', 'phone'), ('profiles', 'avatar_url'),
    ('crime_reports', 'user_id'), ('crime_reports', 'category'),
    ('crime_reports', 'title'), ('crime_reports', 'description'),
    ('crime_reports', 'incident_date_time'), ('crime_reports', 'latitude'),
    ('crime_reports', 'longitude'), ('crime_reports', 'location_name'),
    ('crime_reports', 'status'), ('crime_reports', 'verified'),
    ('emergency_contacts', 'user_id'), ('emergency_contacts', 'name'),
    ('emergency_contacts', 'phone'), ('emergency_contacts', 'email'),
    ('emergency_contacts', 'relationship'),
    ('sos_hot_words', 'user_id'), ('sos_hot_words', 'hot_word')
) as x(tbl, col)
left join information_schema.columns c
       on c.table_schema = 'public'
      and c.table_name   = x.tbl
      and c.column_name  = x.col
order by x.tbl, x.col;


-- ---------------------------------------------------------------------------
-- 6. Foreign keys cascade from auth.users
-- ---------------------------------------------------------------------------
-- Without ON DELETE CASCADE, deleting a user leaves orphaned personal data —
-- which is both a bug and a privacy problem.
select
    tc.table_name,
    rc.delete_rule,
    case when rc.delete_rule = 'CASCADE' then '✅ OK' else '❌ expected CASCADE' end as status
from information_schema.table_constraints tc
join information_schema.referential_constraints rc
     on rc.constraint_name = tc.constraint_name
    and rc.constraint_schema = tc.table_schema
where tc.constraint_type = 'FOREIGN KEY'
  and tc.table_schema = 'public'
  and tc.table_name in (
      'profiles', 'crime_reports', 'emergency_contacts', 'sos_hot_words',
      'users', 'sos_incidents', 'user_locations'
  )
order by tc.table_name;


-- ---------------------------------------------------------------------------
-- 7. Storage bucket
-- ---------------------------------------------------------------------------
select
    'avatars bucket' as check_name,
    case
        when not exists (select 1 from storage.buckets where id = 'avatars')
            then '❌ MISSING'
        when not (select public from storage.buckets where id = 'avatars')
            then '❌ FAIL — not public, getPublicUrl() will not work'
        else '✅ OK'
    end as status;

select
    'avatars policies' as check_name,
    count(*) as policies,
    case when count(*) = 4 then '✅ OK' else '❌ expected 4' end as status
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
  and policyname like 'avatars_%';


-- ---------------------------------------------------------------------------
-- 8. PostGIS
-- ---------------------------------------------------------------------------
select
    'postgis extension' as check_name,
    case when exists (select 1 from pg_extension where extname = 'postgis')
         then '✅ OK'
         else '⚠️  NOT INSTALLED — fine for now; nothing writes geography yet' end as status;
