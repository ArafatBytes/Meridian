-- ===========================================================================
-- 20261015190000__guardian_notice_outlives_the_contact
-- JG3 — a contact you used once stays deletable
-- ===========================================================================
-- Drops `journeys_notice_needs_guardian`, added one migration ago in
-- `20261015180000__journey_guardian.sql`. It was wrong, and it was wrong in a
-- way that broke an unrelated screen permanently.
--
-- ---------------------------------------------------------------------------
-- What it did
-- ---------------------------------------------------------------------------
-- The CHECK said:
--
--     (started_notice_at is null and arrived_notice_at is null)
--     or guardian_contact_id is not null
--
-- "A notice cannot have been sent about a journey with no guardian." Read as a
-- statement about the moment a notice is sent, that is correct and is what the
-- sweep enforces anyway -- every notice query inner-joins
-- `emergency_contacts` through `guardian_contact_id`, so a journey with no
-- guardian is never selected by any of them.
--
-- Read as a statement about a **row**, which is what a CHECK is, it is false:
-- the schema's own foreign key produces the state it forbids.
-- `journeys_guardian_contact_fk` is `on delete set null`, deliberately, so
-- deleting a contact turns their old journeys into "no guardian" rather than
-- leaving a dangling id. On a journey whose guardian had already been emailed,
-- that set-null left `started_notice_at` populated with
-- `guardian_contact_id` null -- and the CHECK rejected it.
--
-- The consequence was not a rejected journey. It was a rejected **DELETE**:
--
--     delete from public.emergency_contacts where id = ...
--     ERROR:  new row for relation "journeys" violates check constraint
--             "journeys_notice_needs_guardian"
--
-- So any contact ever used as a guardian on a journey that got as far as its
-- "she set off" email -- which is every such journey, one minute after Start --
-- became undeletable, and the contacts screen could only report "Failed to
-- delete contact" with no way for anybody to work out why. `on delete set
-- null` had been turned into `on delete restrict` by a CHECK two sections
-- further down the same file, which is precisely what that file's own comment
-- said it was avoiding: *"a blocked delete"*. Its test said the same thing --
-- *"restrict would make a contact undeletable while any old journey pointed at
-- them, which turns 'remove this person from my life' into an error message"* --
-- and passed, because it read the FK clause and never ran a delete.
--
-- Found by running the delete against the real table in a rolled-back
-- transaction. Nothing in 741 tests could see it: both halves were separately
-- correct, and only the database knew they were contradictory.
--
-- ---------------------------------------------------------------------------
-- Why dropping it loses nothing
-- ---------------------------------------------------------------------------
-- The rule it was trying to state is "nobody is told about a journey with no
-- guardian", which has nothing to do with the timestamps and is enforced where
-- the telling happens:
--
-- * `_PENDING_STARTED_NOTICE`, `_PENDING_ARRIVED_NOTICE` and
--   `_ESCALATION_RECIPIENTS` in `app/agents/journey_watch.py` all join
--   `emergency_contacts` on `guardian_contact_id`. No guardian, no row, no
--   message -- at any ring, including the last.
-- * The heartbeat refuses to store a position without a guardian, in the same
--   `UPDATE` that writes it, and the app refuses to send one. That is the
--   privacy rule, and it is untouched by this file.
--
-- What the dropped CHECK uniquely asserted was that a *historical* notice
-- implies a *current* guardian, and that is simply not true of a row whose
-- guardian has since been deleted. Expressing "a guardian was chosen once"
-- would need a second column holding a copy of the contact, which is the
-- denormalisation `20261015180000` explains at length why it did not do.
--
-- A journey in that state is readable and honest: the timestamps say a message
-- was sent, `guardian_contact_id` is null, and the journey screen says
-- "Telling your guardian" rather than naming somebody who no longer exists.

do $c$
begin
    if not exists (
        select 1 from information_schema.tables
         where table_schema = 'public' and table_name = 'journeys'
    ) then
        raise exception
            'public.journeys is missing; apply 20261014150000__journeys.sql first';
    end if;

    -- Guard, not a silent skip. If this constraint is not here, either
    -- 20261015180000 has not been applied -- in which case the ladder, the
    -- notice columns and the position do not exist either and this file is
    -- being run far out of order -- or somebody dropped it by hand and should
    -- know that this migration was going to.
    if not exists (
        select 1 from pg_constraint where conname = 'journeys_notice_needs_guardian'
    ) then
        raise notice
            'journeys_notice_needs_guardian is already absent; nothing to drop';
    end if;
end $c$;


alter table public.journeys
    drop constraint if exists journeys_notice_needs_guardian;


-- The rest of 20261015180000's CHECKs stay exactly as they are. They are all
-- statements about one row at one instant -- `escalation_state` against its own
-- timestamp, each rung after the one below it, a position with its time -- and
-- none of them is contradicted by a foreign key.
