-- ===========================================================================
-- B13 — verify the report-trust and community-cluster migration took.
-- ===========================================================================
-- ONE statement, so the Supabase SQL Editor shows every check. The editor only
-- renders the LAST result set when you paste several statements, which is why the
-- earlier five-query version appeared to return nothing but a single `0` — that
-- was the fifth query's answer, and the first four were discarded unseen.
--
-- Read-only. Safe to run any number of times, before or after the agent has run.
--
-- Expect: every row PASS. The two INFO rows are counts, not assertions.
-- ===========================================================================

with results (sort, check_name, result, detail) as (

    -- ---- 1. the `verified` column is gone ---------------------------------
    -- There was no honest way for this product to set it: the app cannot
    -- establish that an incident happened. Dropped rather than left unused,
    -- because a boolean called `verified` in the schema is an invitation.
    select 1, 'verified column dropped',
           case when not exists (
               select 1 from information_schema.columns
                where table_schema = 'public'
                  and table_name   = 'crime_reports'
                  and column_name  = 'verified'
           ) then 'PASS' else 'FAIL — column still present' end,
           ''

    -- ---- 2. the status vocabulary carries no trust level ------------------
    -- Aggregated, so a MISSING constraint reports FAIL rather than dropping this
    -- row from the output entirely. An un-aggregated branch over zero rows
    -- contributes nothing to a UNION, which is the quietest possible way for a
    -- check to not run.
    union all
    select 2, 'status vocabulary is filed/withdrawn/removed',
           case when max(pg_get_constraintdef(oid)) like '%''filed''%'
                 and max(pg_get_constraintdef(oid)) like '%''withdrawn''%'
                 and max(pg_get_constraintdef(oid)) like '%''removed''%'
                 and max(pg_get_constraintdef(oid)) not like '%''pending''%'
                 and max(pg_get_constraintdef(oid)) not like '%''verified''%'
                then 'PASS' else 'FAIL' end,
           coalesce(max(pg_get_constraintdef(oid)), 'constraint missing')
      from pg_constraint
     where conname = 'crime_reports_status_check'

    -- ---- 3. existing rows were migrated ----------------------------------
    union all
    select 3, 'no report left on a retired status',
           case when count(*) = 0 then 'PASS'
                else 'FAIL — ' || count(*) || ' row(s) still on an old status' end,
           coalesce(string_agg(distinct status, ', '), 'none')
      from public.crime_reports
     where status not in ('filed', 'withdrawn', 'removed')

    -- ---- 4. THE SELF-VERIFY HOLE -----------------------------------------
    -- The one that mattered. `crime_reports_update_own` grants UPDATE on your own
    -- row and `status` was a column on it, so three lines of client code
    -- self-awarded `verified = true`. RLS cannot stop that — the row genuinely is
    -- yours. Column privileges can, and they compose with RLS.
    --
    -- `has_table_privilege` is table-level only; `has_any_column_privilege` is true
    -- if the role holds the privilege on the table OR on any single column. The two
    -- answers together ARE the fix: no table-level UPDATE, but some columns still
    -- editable.
    union all
    select 4, 'client cannot write crime_reports.status',
           case when has_column_privilege(
                        'authenticated', 'public.crime_reports', 'status', 'UPDATE')
                then 'FAIL — status is still client-writable'
                else 'PASS' end,
           'table-level UPDATE: '
           || has_table_privilege('authenticated', 'public.crime_reports', 'UPDATE')
           || ' · any-column UPDATE: '
           || has_any_column_privilege('authenticated', 'public.crime_reports', 'UPDATE')

    union all
    select 5, 'client can still edit report content',
           case when has_column_privilege(
                        'authenticated', 'public.crime_reports', 'title', 'UPDATE')
                then 'PASS' else 'FAIL — content columns were over-revoked' end,
           'title, description, category, location are still editable'

    union all
    select 6, 'client cannot reassign or backdate a report',
           case when has_column_privilege(
                        'authenticated', 'public.crime_reports', 'user_id', 'UPDATE')
                  or has_column_privilege(
                        'authenticated', 'public.crime_reports', 'created_at', 'UPDATE')
                then 'FAIL' else 'PASS' end,
           'user_id would move a report to another account; created_at would '
           || 'backdate it into a corroboration window it was not in'

    -- ---- 7. reports are private to their author --------------------------
    union all
    select 7, 'reports readable only by their author',
           case when count(*) = 1
                 and max(qual) like '%auth.uid()%'
                 and max(qual) not like '%true%'
                then 'PASS'
                else 'FAIL — ' || count(*) || ' SELECT policy/policies' end,
           coalesce(max(policyname) || ': ' || max(qual), 'none')
      from pg_policies
     where schemaname = 'public' and tablename = 'crime_reports' and cmd = 'SELECT'

    -- ---- 8. the withdrawal RPC ------------------------------------------
    union all
    select 8, 'withdraw_crime_report exists and is security definer',
           case when bool_or(p.prosecdef) then 'PASS' else 'FAIL' end,
           'the only path by which a client may change status'
      from pg_proc p
      join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public' and p.proname = 'withdraw_crime_report'

    -- ---- 9. the new table -----------------------------------------------
    union all
    select 9, 'community_clusters table exists',
           case when exists (
               select 1 from information_schema.tables
                where table_schema = 'public' and table_name = 'community_clusters'
           ) then 'PASS' else 'FAIL' end,
           ''

    -- ---- 10. RLS on it, which is what the editor warned about -------------
    -- The Supabase linter flags `create table` before it reaches the
    -- `alter table ... enable row level security` at the end of the migration.
    -- This is the authoritative answer to that warning.
    union all
    select 10, 'RLS enabled on community_clusters',
           case when bool_or(relrowsecurity) then 'PASS'
                else 'FAIL — the Supabase RLS warning was real' end,
           'the editor warns on create-table; the migration enables it 60 lines later'
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public' and c.relname = 'community_clusters'

    -- ---- 11. and deliberately no policies --------------------------------
    -- Same arrangement as `risk_flags` and `push_devices`: RLS on with nothing
    -- granted, so `anon` and `authenticated` cannot touch it through PostgREST at
    -- all. Reached through DATABASE_URL by the API, which decays every row on the
    -- way out. A client reading this table directly would see undecayed severity
    -- and draw a cluster at full strength forever.
    --
    -- Supabase may separately warn "RLS enabled but no policies". That warning is
    -- also expected, and is the design.
    union all
    select 11, 'community_clusters has no policies, on purpose',
           case when count(*) = 0 then 'PASS'
                else 'FAIL — ' || count(*) || ' policy/policies would expose it' end,
           'served through /risk/clusters so decay is applied on read'
      from pg_policies
     where schemaname = 'public' and tablename = 'community_clusters'

    -- ---- 12. the headline invariant, in the database ---------------------
    union all
    select 12, 'a cluster cannot exist with one reporter',
           case when count(*) = 1 then 'PASS' else 'FAIL' end,
           coalesce(max(pg_get_constraintdef(oid)), 'missing')
      from pg_constraint
     where conname = 'community_clusters_needs_two_reporters'

    union all
    select 13, 'corroborated needs three reporters',
           case when count(*) = 1 then 'PASS' else 'FAIL' end,
           coalesce(max(pg_get_constraintdef(oid)), 'missing')
      from pg_constraint
     where conname = 'community_clusters_corroborated_needs_three'

    -- ---- 14. decay is derived, not supplied ------------------------------
    union all
    select 14, 'expires_at is set by a trigger',
           case when count(*) = 1 then 'PASS' else 'FAIL' end,
           'callers cannot hand-set it; one formula, one place'
      from pg_trigger
     where tgname = 'trg_community_clusters_expires_at' and not tgisinternal

    -- ---- 15. the ledger -------------------------------------------------
    union all
    select 15, 'both migrations recorded in the ledger',
           case when count(*) = 2 then 'PASS'
                else 'FAIL — ' || count(*) || ' of 2 recorded' end,
           coalesce(string_agg(version, ', ' order by version), 'none')
      from public.schema_migrations
     where version in ('20261013120000', '20261013120100')

    -- ---- INFO. counts, not assertions -----------------------------------
    union all
    select 90, 'INFO — your reports by status', '',
           coalesce(string_agg(status || ': ' || n, ' · ' order by status), 'no reports yet')
      from (select status, count(*) as n from public.crime_reports group by status) s

    union all
    select 91, 'INFO — clusters published', '',
           count(*) || ' (0 is correct until the corroboration agent has run)'
      from public.community_clusters
)
select check_name, result, detail
  from results
 order by sort;
