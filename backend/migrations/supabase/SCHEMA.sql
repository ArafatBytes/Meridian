-- ============================================================================
-- Meridian — Fresh Supabase schema
-- ============================================================================
-- Everything the CURRENT implementation needs in order to run. Nothing more.
--
-- Run this once, in the Supabase SQL Editor, on a fresh project.
-- See README.md in this directory for the full setup order and the
-- Auth settings you must change by hand.
--
-- Idempotent: safe to re-run. To start completely over, run RESET.sql first.
--
-- Scope note: this schema matches the code as it exists today, including two
-- warts that ADR 0003 and ADR 0004 (sprint S02) will clean up:
--   * `public.users` duplicates `public.profiles` — the backend writes one,
--     the app writes the other. Marked TRANSITIONAL below.
--   * `crime_reports.latitude/longitude` are varchar, not numeric/geography,
--     because that is what the app sends and the ORM declares.
-- Do not "fix" either here. They are scheduled.
-- ============================================================================


-- ============================================================================
-- 0. EXTENSIONS
-- ============================================================================

-- PostGIS backs the `geography` columns on sos_incidents and user_locations
-- (geoalchemy2 models in backend/app/models/). Supabase convention is to
-- install extensions outside `public`.
--
-- Nothing in the current code writes to those two tables, so if PostGIS is
-- unavailable on your plan you may comment out this line and section 5.3/5.4.
create extension if not exists postgis with schema extensions;


-- ============================================================================
-- 1. profiles  — the app's user profile table
-- ============================================================================
-- Written by: frontend only (auth.service.ts, EditProfileScreen.tsx)
-- Identity lives in auth.users; this holds the display fields.

create table if not exists public.profiles (
    id          uuid primary key references auth.users (id) on delete cascade,
    email       text        not null,
    name        text        not null,
    phone       text,
    avatar_url  text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

comment on table public.profiles is
    'App-facing user profile. Identity is auth.users; this is display data.';


-- ============================================================================
-- 2. crime_reports  — community crime reports
-- ============================================================================
-- Written by: frontend (crime.service.ts)
-- Read by:    frontend (map shows ALL users' reports) + backend route_service

do $$
begin
    create type public.crime_category as enum (
        'theft',
        'assault',
        'harassment',
        'vandalism',
        'burglary',
        'robbery',
        'fraud',
        'other'
    );
exception
    when duplicate_object then null;
end $$;

-- NOTE: values are lowercase. The app's AddReportScreen sends lowercase ids;
-- frontend/src/types/index.ts and MapScreen's CRIME_COLORS use capitalised
-- variants, which is why map markers currently render with no colour.
-- That is Defect 3, fixed in S07 — the database is correct, the client is not.

create table if not exists public.crime_reports (
    id                 uuid primary key default gen_random_uuid(),
    user_id            uuid        not null references auth.users (id) on delete cascade,
    category           public.crime_category not null,
    title              varchar(200) not null,
    description        text        not null,
    incident_date_time timestamp   not null,
    latitude           varchar     not null,
    longitude          varchar     not null,
    location_name      varchar,
    status             varchar     not null default 'pending',
    verified           boolean     not null default false,
    created_at         timestamp   not null default now(),
    updated_at         timestamp   not null default now(),

    constraint crime_reports_status_check
        check (status in ('pending', 'verified', 'investigating', 'resolved'))
);

-- `timestamp` (no time zone) is deliberate: it matches the naive DateTime in
-- backend/app/models/crime.py, and the app encodes Bangladesh local time as if
-- it were UTC. That encoding is itself a latent bug, tracked for S07 — the
-- column type must not change before the client does.

create index if not exists idx_crime_reports_user_id
    on public.crime_reports (user_id);
create index if not exists idx_crime_reports_category
    on public.crime_reports (category);
create index if not exists idx_crime_reports_incident_date_time
    on public.crime_reports (incident_date_time);
create index if not exists idx_crime_reports_created_at
    on public.crime_reports (created_at desc);
create index if not exists idx_crime_reports_status
    on public.crime_reports (status);


-- ============================================================================
-- 3. emergency_contacts  — SOS recipients
-- ============================================================================
-- Written by: frontend (EmergencyContactsScreen.tsx)
-- Read by:    backend sos_service.py  ← this is what makes SOS work

create table if not exists public.emergency_contacts (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references auth.users (id) on delete cascade,
    name         varchar not null,
    phone        varchar not null,
    email        varchar not null,
    relationship varchar,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- `email` is NOT NULL because sos_service.py has no fallback channel: a
-- contact without an email is a contact that cannot be alerted.
-- `relationship` is nullable — the ORM declares it, the app never sends it.

create index if not exists idx_emergency_contacts_user_id
    on public.emergency_contacts (user_id);


-- ============================================================================
-- 4. sos_hot_words  — user-configured SOS trigger phrases
-- ============================================================================
-- Written by: frontend (SOSHotWordsScreen.tsx)
-- Read by:    NOTHING YET.
--
-- These phrases are stored and never consumed: /voice/analyze hardcodes its own
-- list and returns an empty transcript unconditionally. The table is created so
-- the existing screen works; S18 is what makes the words actually do something.

create table if not exists public.sos_hot_words (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references auth.users (id) on delete cascade,
    hot_word   text not null,
    created_at timestamptz not null default now(),

    constraint sos_hot_words_unique_per_user unique (user_id, hot_word)
);

create index if not exists idx_sos_hot_words_user_id
    on public.sos_hot_words (user_id);


-- ============================================================================
-- 5. BACKEND-ONLY TABLES
-- ============================================================================
-- These are reached exclusively through DATABASE_URL (SQLAlchemy), never
-- through PostgREST. RLS is enabled with no policies, so the anon and
-- authenticated roles cannot touch them at all; the service role bypasses RLS.

-- ---------------------------------------------------------------------------
-- 5.1 users  ***TRANSITIONAL — scheduled for deletion in S02 (ADR 0003)***
-- ---------------------------------------------------------------------------
-- backend/app/api/v1/endpoints/sos.py auto-provisions a row here on first SOS,
-- duplicating data that already lives in auth.users + public.profiles.
-- It exists only so SOS runs today. Do not build anything new on it.

create table if not exists public.users (
    id            uuid primary key references auth.users (id) on delete cascade,
    email         varchar not null unique,
    full_name     varchar not null,
    phone         varchar not null,
    password_hash varchar not null,
    hot_words     json    not null default '["help","bachao","save me","police"]'::json,
    is_active     boolean not null default true,
    is_verified   boolean not null default false,
    created_at    timestamp not null default now(),
    updated_at    timestamp not null default now()
);

comment on table public.users is
    'TRANSITIONAL. Duplicates profiles. Deleted in S02 per docs/adr/0003. '
    'password_hash is always the literal "supabase_managed" — Supabase owns auth.';

-- ---------------------------------------------------------------------------
-- 5.2 sos_incidents
-- ---------------------------------------------------------------------------
-- The model exists; nothing writes it yet, so the README's claim that SOS
-- incidents are "logged in database" is currently false. S05 makes it true.

create table if not exists public.sos_incidents (
    id                uuid primary key default gen_random_uuid(),
    user_id           uuid not null references auth.users (id) on delete cascade,
    location          extensions.geography(Point, 4326) not null,
    video_url         varchar,
    police_station_id varchar,
    contacts_notified text,
    voice_activated   boolean not null default false,
    status            varchar not null default 'active',
    timestamp         timestamp not null default now(),
    resolved_at       timestamp,

    constraint sos_incidents_status_check
        check (status in ('active', 'resolved', 'false_alarm'))
);

create index if not exists idx_sos_incidents_user_id
    on public.sos_incidents (user_id);
create index if not exists idx_sos_incidents_timestamp
    on public.sos_incidents (timestamp desc);
create index if not exists idx_sos_incidents_location
    on public.sos_incidents using gist (location);

-- ---------------------------------------------------------------------------
-- 5.3 user_locations
-- ---------------------------------------------------------------------------
-- Nothing writes this yet either — background tracking lands in S17, and the
-- retention window from app/privacy/retention.py (S03) applies to it.

create table if not exists public.user_locations (
    id        uuid primary key default gen_random_uuid(),
    user_id   uuid not null references auth.users (id) on delete cascade,
    location  extensions.geography(Point, 4326) not null,
    accuracy  double precision,
    timestamp timestamp not null default now()
);

create index if not exists idx_user_locations_user_id
    on public.user_locations (user_id);
create index if not exists idx_user_locations_timestamp
    on public.user_locations (timestamp desc);
create index if not exists idx_user_locations_location
    on public.user_locations using gist (location);


-- ============================================================================
-- 6. updated_at TRIGGERS
-- ============================================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
    before update on public.profiles
    for each row execute function public.set_updated_at();

drop trigger if exists trg_crime_reports_updated_at on public.crime_reports;
create trigger trg_crime_reports_updated_at
    before update on public.crime_reports
    for each row execute function public.set_updated_at();

drop trigger if exists trg_emergency_contacts_updated_at on public.emergency_contacts;
create trigger trg_emergency_contacts_updated_at
    before update on public.emergency_contacts
    for each row execute function public.set_updated_at();

drop trigger if exists trg_users_updated_at on public.users;
create trigger trg_users_updated_at
    before update on public.users
    for each row execute function public.set_updated_at();


-- ============================================================================
-- 7. ROW LEVEL SECURITY
-- ============================================================================
-- The app ships the anon key, so RLS is the only thing standing between one
-- user and every other user's data. Every table gets it.

alter table public.profiles            enable row level security;
alter table public.crime_reports       enable row level security;
alter table public.emergency_contacts  enable row level security;
alter table public.sos_hot_words       enable row level security;
alter table public.users               enable row level security;
alter table public.sos_incidents       enable row level security;
alter table public.user_locations      enable row level security;

-- ---- profiles: own row only ------------------------------------------------
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
    for select to authenticated using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
    for insert to authenticated with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
    for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- ---- crime_reports: read everyone's, write only your own -------------------
-- The map is a community crime map: MapScreen.fetchCrimeReports() deliberately
-- queries with no user filter. This SELECT policy is what makes that work.
drop policy if exists "crime_reports_select_all" on public.crime_reports;
create policy "crime_reports_select_all" on public.crime_reports
    for select to authenticated using (true);

drop policy if exists "crime_reports_insert_own" on public.crime_reports;
create policy "crime_reports_insert_own" on public.crime_reports
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "crime_reports_update_own" on public.crime_reports;
create policy "crime_reports_update_own" on public.crime_reports
    for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "crime_reports_delete_own" on public.crime_reports;
create policy "crime_reports_delete_own" on public.crime_reports
    for delete to authenticated using (auth.uid() = user_id);

-- ---- emergency_contacts: own rows only -------------------------------------
drop policy if exists "emergency_contacts_select_own" on public.emergency_contacts;
create policy "emergency_contacts_select_own" on public.emergency_contacts
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "emergency_contacts_insert_own" on public.emergency_contacts;
create policy "emergency_contacts_insert_own" on public.emergency_contacts
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "emergency_contacts_update_own" on public.emergency_contacts;
create policy "emergency_contacts_update_own" on public.emergency_contacts
    for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "emergency_contacts_delete_own" on public.emergency_contacts;
create policy "emergency_contacts_delete_own" on public.emergency_contacts
    for delete to authenticated using (auth.uid() = user_id);

-- ---- sos_hot_words: own rows only ------------------------------------------
drop policy if exists "sos_hot_words_select_own" on public.sos_hot_words;
create policy "sos_hot_words_select_own" on public.sos_hot_words
    for select to authenticated using (auth.uid() = user_id);

drop policy if exists "sos_hot_words_insert_own" on public.sos_hot_words;
create policy "sos_hot_words_insert_own" on public.sos_hot_words
    for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "sos_hot_words_delete_own" on public.sos_hot_words;
create policy "sos_hot_words_delete_own" on public.sos_hot_words
    for delete to authenticated using (auth.uid() = user_id);

-- ---- users / sos_incidents / user_locations --------------------------------
-- Intentionally NO policies. RLS is on, so anon and authenticated are locked
-- out entirely. Only the backend's service-role connection (which bypasses
-- RLS) can read or write these.


-- ============================================================================
-- 8. GRANTS
-- ============================================================================
-- RLS decides which rows; grants decide which tables are visible to PostgREST
-- at all. Backend-only tables are granted to nobody.

grant select, insert, update          on public.profiles           to authenticated;
grant select, insert, update, delete  on public.crime_reports      to authenticated;
grant select, insert, update, delete  on public.emergency_contacts to authenticated;
grant select, insert, delete          on public.sos_hot_words      to authenticated;

revoke all on public.users          from anon, authenticated;
revoke all on public.sos_incidents  from anon, authenticated;
revoke all on public.user_locations from anon, authenticated;


-- ============================================================================
-- 9. STORAGE — avatars bucket
-- ============================================================================
-- EditProfileScreen uploads to bucket 'avatars' at path '<uid>/<filename>'
-- and then calls getPublicUrl, so the bucket must be public-read.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'avatars',
    'avatars',
    true,
    5242880,  -- 5 MB, matching MAX_IMAGE_SIZE in app.constants.ts
    array['image/jpeg', 'image/png', 'image/webp', 'image/heic']
)
on conflict (id) do update
    set public             = excluded.public,
        file_size_limit    = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;

-- Write access is scoped to a folder named after the user's own uid, which is
-- exactly the path EditProfileScreen builds. Without this, one user could
-- overwrite another's avatar.
drop policy if exists "avatars_insert_own_folder" on storage.objects;
create policy "avatars_insert_own_folder" on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

drop policy if exists "avatars_update_own_folder" on storage.objects;
create policy "avatars_update_own_folder" on storage.objects
    for update to authenticated
    using (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

drop policy if exists "avatars_delete_own_folder" on storage.objects;
create policy "avatars_delete_own_folder" on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

drop policy if exists "avatars_public_read" on storage.objects;
create policy "avatars_public_read" on storage.objects
    for select to public
    using (bucket_id = 'avatars');


-- ============================================================================
-- 10. RELOAD POSTGREST SCHEMA CACHE
-- ============================================================================
-- Without this, PostgREST can report "column X does not exist in the schema
-- cache" for minutes after a DDL change. This is the fix that
-- SUPABASE_SCHEMA_CACHE_FIX.md was written about.

notify pgrst, 'reload schema';


-- ============================================================================
-- Done. Run VERIFY.sql to confirm.
-- ============================================================================
