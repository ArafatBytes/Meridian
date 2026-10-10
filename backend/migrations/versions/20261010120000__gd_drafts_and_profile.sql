-- ===========================================================================
-- D08 — the General Diary draft, and the five fields the form demands
-- ===========================================================================
-- ADR 0007. Meridian drafts a GD application; a person files it. Nothing here
-- transmits anything to anyone, and there is deliberately no `filed` state --
-- we cannot know that a GD was filed, so we do not claim it. What we can know
-- is the number the duty officer wrote on the copy he handed back, because the
-- user types it in. That is `gd_number`: a record, not a state.
--
-- Two changes: a table for the drafts, and five columns on `users`.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. The GD profile
-- ---------------------------------------------------------------------------
-- The official DMP form (docs/reference/dmp-gd-form.pdf) requires these five
-- above the narrative, and we store none of them. They are not derivable from
-- anything we hold and they are not guessable -- a wrong NID or a wrong
-- father's name on a police application is the user's problem, signed in their
-- own hand. So they are typed once, by the person they belong to.
--
-- On `users` rather than in a table of their own: it is strictly 1:1, it is
-- five columns, and a second table would buy a join and nothing else.
--
-- All nullable. A user who never files a GD never fills these in, and the
-- draft endpoint refuses rather than inventing a default.

alter table public.users
    add column if not exists gd_nid text,
    add column if not exists gd_father_name text,
    add column if not exists gd_mother_name text,
    add column if not exists gd_permanent_address text,
    add column if not exists gd_present_address text;

comment on column public.users.gd_nid is
    'জাতীয় পরিচয় পত্র নং as the user typed it. Never validated against the '
    'Election Commission -- we have no access and no business checking. Stored '
    'because the GD form has a field for it, and used nowhere else.';

comment on column public.users.gd_father_name is 'পিতা, as the DMP form asks for it.';
comment on column public.users.gd_mother_name is 'মাতা, as the DMP form asks for it.';
comment on column public.users.gd_permanent_address is 'ঠিকানা (স্থায়ী).';
comment on column public.users.gd_present_address is
    'ঠিকানা (বর্তমান). The form asks for both addresses separately and they are '
    'routinely different in Bangladesh, so they are two columns and not one.';


-- ---------------------------------------------------------------------------
-- 2. The drafts
-- ---------------------------------------------------------------------------

create table if not exists public.gd_drafts (
    id                uuid primary key default gen_random_uuid(),
    report_id         uuid not null references public.crime_reports(id) on delete cascade,
    user_id           uuid not null references public.users(id) on delete cascade,

    state             text not null default 'draft',
    narrative_bn      text not null,
    summary_en        text not null,
    missing_details   jsonb not null default '[]'::jsonb,

    thana_name        text not null,
    thana_district    text not null,

    engine            text not null,
    approved_at       timestamptz,
    gd_number         text,
    gd_filed_at       timestamptz,

    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),

    -- The state machine, in the database rather than in the UI. A disabled
    -- button is a courtesy; this is the rule. Two states only: there is no
    -- `filed`, because filing happens at a thana counter we cannot observe.
    constraint gd_drafts_state_known
        check (state in ('draft', 'ready_to_file')),

    -- Approval is what moves it, and approval has a timestamp. Neither can
    -- exist without the other, in either direction -- which is what makes
    -- "approved" impossible to fake by writing one column.
    constraint gd_drafts_approved_iff_ready
        check ((state = 'ready_to_file') = (approved_at is not null)),

    -- A GD number can only come back from a document that was actually taken
    -- to a thana, and only an approved draft can be taken anywhere.
    constraint gd_drafts_number_needs_approval
        check (gd_number is null or state = 'ready_to_file'),

    constraint gd_drafts_filed_at_needs_number
        check ((gd_number is null) = (gd_filed_at is null))
);

-- One draft per report. Regenerating replaces the draft rather than
-- accumulating variants, and the API only allows that while it is still
-- `draft` -- so an approved document cannot be swapped out from under its
-- approval.
create unique index if not exists idx_gd_drafts_one_per_report
    on public.gd_drafts (report_id);

create index if not exists idx_gd_drafts_by_user
    on public.gd_drafts (user_id, created_at desc);

comment on table public.gd_drafts is
    'General Diary application drafts. One per report. Meridian generates the '
    'narrative and names the thana; a person reads it, approves it, prints it '
    'and files it. See docs/adr/0007-d08-casework-gd.md.';

comment on column public.gd_drafts.narrative_bn is
    'The formal Bangla body of the application. Goes between the two fixed '
    'lines of the DMP form, and into the Online GD app''s বিবরণ box unchanged. '
    'Editable by the user while state = draft; frozen on approval.';

comment on column public.gd_drafts.missing_details is
    'Facts a duty officer will ask for that the report did not contain. Shown '
    'to the user as prompts before approval. Advisory -- an incomplete GD is '
    'still a GD, and a user who does not know a detail cannot invent one.';

comment on column public.gd_drafts.thana_name is
    'Nearest station to the incident coordinates, from police_stations.csv. '
    'The name only. That file''s email and phone columns are one placeholder '
    'repeated across every row and are never shown to anyone (DEMO_PLAN 7.2).';

comment on column public.gd_drafts.engine is
    'Which tier produced this draft -- `gemini`, `groq`, or a replay fixture. '
    'Kept so a draft that reads oddly can be traced to the model that wrote it.';

comment on column public.gd_drafts.gd_number is
    'The number the duty officer wrote on the copy he handed back, typed in by '
    'the user afterwards. This is the only evidence we ever have that a GD was '
    'filed, and it is hearsay from the only person who was there. We do not '
    'file, so we do not know -- we record what we are told.';
