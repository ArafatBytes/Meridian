-- ===========================================================================
-- D08 fix — the GD profile was hung on the wrong users table
-- ===========================================================================
-- The D08 migration earlier today put five columns on `public.users` and
-- pointed `gd_drafts.user_id` at `public.users(id)`, arguing that a separate
-- table "buys a join and nothing else".
--
-- That reasoning was built on a wrong assumption. **`public.users` is not the
-- user table.** `crime_reports.user_id` references `auth.users(id)`, Supabase's
-- own; `public.users` is a mirror that is not reliably populated. Today it holds
-- two rows, and one account that has filed a report is not one of them.
--
-- So the earlier schema produced, for such an account:
--   * `GET /casework/profile` -> 404, because there is no `public.users` row;
--   * and, had it got that far, a foreign key violation on the first draft,
--     because `gd_drafts.user_id` demanded a row that does not exist.
--
-- A user who can file a report must be able to draft a GD from it. This moves
-- both to `auth.users`, which is where the reports already point.
--
-- It also adds `full_name` and `phone` to the profile. They were being read off
-- `public.users`, which may not exist -- and where it does exist the name is
-- whatever registration stored (one row reads `nakib1990saleh`, an email local
-- part). A General Diary is signed; the name on it is the complainant's to
-- write, not ours to derive.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. The profile, keyed on the table the reports already use
-- ---------------------------------------------------------------------------

create table if not exists public.gd_profiles (
    user_id              uuid primary key references auth.users(id) on delete cascade,

    full_name            text,
    phone                text,
    gd_nid               text,
    gd_father_name       text,
    gd_mother_name       text,
    gd_permanent_address text,
    gd_present_address   text,

    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);

comment on table public.gd_profiles is
    'What the official DMP General Diary form asks for above the narrative, '
    'typed once by the person it belongs to. Keyed on auth.users because that '
    'is what crime_reports uses: anyone who can file a report can draft a GD '
    'from it. Never sent to a model -- the drafting call sees the incident and '
    'nothing else. See docs/adr/0007-d08-casework-gd.md.';

comment on column public.gd_profiles.gd_nid is
    'জাতীয় পরিচয় পত্র নং as the user typed it. Never validated against the '
    'Election Commission -- we have no access and no business checking.';

comment on column public.gd_profiles.full_name is
    'The name that goes on the application, as the complainant writes it. Not '
    'taken from the login: a GD is signed, and the signature has to match.';


-- Carry over anything already typed into the old columns. Only rows that have
-- a matching auth user can move; in practice this is empty, because the feature
-- shipped and was corrected on the same day.
insert into public.gd_profiles (
    user_id, full_name, phone, gd_nid, gd_father_name, gd_mother_name,
    gd_permanent_address, gd_present_address
)
select u.id, u.full_name, u.phone, u.gd_nid, u.gd_father_name, u.gd_mother_name,
       u.gd_permanent_address, u.gd_present_address
from public.users u
join auth.users a on a.id = u.id
where coalesce(u.gd_nid, u.gd_father_name, u.gd_mother_name,
               u.gd_permanent_address, u.gd_present_address) is not null
on conflict (user_id) do nothing;


alter table public.users
    drop column if exists gd_nid,
    drop column if exists gd_father_name,
    drop column if exists gd_mother_name,
    drop column if exists gd_permanent_address,
    drop column if exists gd_present_address;


-- ---------------------------------------------------------------------------
-- 2. Point the drafts at the same place the reports point
-- ---------------------------------------------------------------------------
-- Without this, an account with no `public.users` row cannot have a draft at
-- all -- the insert fails on a foreign key, after the model call has already
-- been paid for.

alter table public.gd_drafts
    drop constraint if exists gd_drafts_user_id_fkey;

alter table public.gd_drafts
    add constraint gd_drafts_user_id_fkey
    foreign key (user_id) references auth.users(id) on delete cascade;
