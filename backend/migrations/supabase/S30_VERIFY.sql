-- ===========================================================================
-- S30 — verify the news-crime migration took.
-- ===========================================================================
-- ONE statement, so the Supabase SQL Editor shows every check. The editor only
-- renders the LAST result set when you paste several statements, which is why a
-- multi-query version appears to return nothing but a single number — that is the
-- last query's answer and the earlier ones are discarded unseen.
--
-- Read-only. Safe to run any number of times, before or after the agent has run.
--
-- Expect: every row PASS. The INFO rows are counts, not assertions, and zero is
-- the correct answer until the Live Risk Agent has read an article reporting a
-- crime at a place the gazetteer knows.
-- ===========================================================================

with results (sort, check_name, result, detail) as (

    -- ---- 1. the published surface exists ----------------------------------
    select 1, 'news_crime_incidents table exists',
           case when exists (
               select 1 from information_schema.tables
                where table_schema = 'public' and table_name = 'news_crime_incidents'
           ) then 'PASS' else 'FAIL — table missing' end,
           ''

    -- ---- 2. the audit trail exists ----------------------------------------
    -- Separate from extracted_incidents on purpose: that table's kind CHECK and
    -- NOT NULL mobility_impact are mobility-only, and writing a crime there would
    -- mean claiming a robbery has a traffic impact.
    union all
    select 2, 'extracted_crimes table exists',
           case when exists (
               select 1 from information_schema.tables
                where table_schema = 'public' and table_name = 'extracted_crimes'
           ) then 'PASS' else 'FAIL — table missing' end,
           ''

    -- ---- 3. THE headline invariant: attribution is enforced in the database -
    -- This is the constraint that makes publishing crime vocabulary admissible.
    -- Without it, nothing stops a statement that asserts a crime occurred without
    -- saying who reported it.
    union all
    select 3, 'statement must name a publisher',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_statement_is_attributed'
           ) then 'PASS' else 'FAIL — the attribution CHECK is missing' end,
           ''

    -- ---- 4. no narrative: the length cap --------------------------------
    union all
    select 4, 'statement length is capped at 160',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_statement_length'
           ) then 'PASS' else 'FAIL — length CHECK missing' end,
           ''

    -- ---- 5. no permanent area labels: decay is mandatory ------------------
    union all
    select 5, 'half life must be positive',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_half_life_positive'
           ) then 'PASS' else 'FAIL — a row could be published that never decays' end,
           ''

    -- ---- 6. no area labels: the radius is capped at 1 km ------------------
    -- A street crime is a corner, not a neighbourhood. risk_flags allows 20 km
    -- because city-wide mobility events exist; nothing here has an analogue.
    union all
    select 6, 'radius capped at 1000 m',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_radius_sane'
           ) then 'PASS' else 'FAIL — radius CHECK missing' end,
           ''

    -- ---- 7. corroboration cannot be faked by writing one column -----------
    union all
    select 7, 'corroborated_at iff two or more sources',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_corroborated_iff_timestamped'
           ) then 'PASS' else 'FAIL — corroboration could be set with one source' end,
           ''

    -- ---- 8. the category vocabulary matches crime_reports -----------------
    -- One vocabulary for a user's own report and a published one. A ninth value
    -- here would be a value the frontend has no colour for.
    union all
    select 8, 'category vocabulary matches crime_reports',
           case when exists (
               select 1 from pg_constraint
                where conname = 'news_crime_incidents_category_check'
                  and pg_get_constraintdef(oid) like '%robbery%'
                  and pg_get_constraintdef(oid) like '%harassment%'
           ) then 'PASS' else 'FAIL — category CHECK missing or changed' end,
           ''

    -- ---- 9. expires_at is derived, not supplied ---------------------------
    -- The trigger overwrites whatever a caller passes. Without it a row could be
    -- inserted with an expiry decades out and would never retire.
    union all
    select 9, 'expires_at trigger installed',
           case when exists (
               select 1 from pg_trigger
                where tgname = 'trg_news_crime_incidents_expires_at'
           ) then 'PASS' else 'FAIL — expires_at would be whatever was supplied' end,
           ''

    -- ---- 10. backend-only ------------------------------------------------
    -- RLS on with no policies: anon and authenticated reach nothing. The app reads
    -- this through GET /api/v1/risk/news-crime, which serves DECAYED severity. A
    -- client reading the table directly would draw every incident at full strength
    -- for ever, which is the one failure the decay design exists to prevent.
    union all
    select 10, 'RLS enabled on news_crime_incidents',
           case when exists (
               select 1 from pg_class c
                 join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public'
                  and c.relname = 'news_crime_incidents'
                  and c.relrowsecurity
           ) then 'PASS' else 'FAIL — table is readable by clients' end,
           ''

    union all
    select 11, 'RLS enabled on extracted_crimes',
           case when exists (
               select 1 from pg_class c
                 join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public'
                  and c.relname = 'extracted_crimes'
                  and c.relrowsecurity
           ) then 'PASS' else 'FAIL — the audit trail is readable by clients' end,
           ''

    -- ---- 12. the spatial index exists ------------------------------------
    -- Every map read is a bounding box and every route read is a corridor; both
    -- are ST_Intersects / ST_DWithin on the geography column.
    union all
    select 12, 'spatial index present',
           case when exists (
               select 1 from pg_indexes
                where schemaname = 'public'
                  and indexname = 'idx_news_crime_incidents_location'
           ) then 'PASS' else 'FAIL — bbox and corridor reads will sequential scan' end,
           ''

    -- ---- 13. the ledger row ----------------------------------------------
    union all
    select 13, 'migration recorded as applied',
           case when exists (
               select 1 from public.schema_migrations where version = '20261014120000'
           ) then 'PASS' else 'FAIL — migrate.py status will not see it' end,
           ''

    -- ---- INFO. counts, not assertions ------------------------------------
    union all
    select 14, 'INFO published incidents',
           'INFO',
           coalesce((select count(*)::text from public.news_crime_incidents
                      where status = 'published'), '0')
           || ' live, '
           || coalesce((select count(*)::text from public.news_crime_incidents
                         where source_count >= 2), '0')
           || ' corroborated by two or more publishers'

    union all
    select 15, 'INFO extractions recorded',
           'INFO',
           coalesce((select count(*)::text from public.extracted_crimes), '0')
           || ' total, '
           || coalesce((select count(*)::text from public.extracted_crimes
                         where discarded_reason is not null), '0')
           || ' read but deliberately not published'

    -- ---- 16. the one that would be a real problem -------------------------
    -- Any published statement that does not name a publisher. The CHECK should
    -- make this impossible; this proves it of the live data rather than asserting
    -- it of the schema.
    union all
    select 16, 'every published statement names its source',
           case when not exists (
               select 1 from public.news_crime_incidents
                where statement not like '% reported by %'
           ) then 'PASS' else 'FAIL — an unattributed claim is published' end,
           ''
)
select check_name, result, detail
  from results
 order by sort;
