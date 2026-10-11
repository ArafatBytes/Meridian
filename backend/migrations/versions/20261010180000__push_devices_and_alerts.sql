-- ===========================================================================
-- B6a / S16 — push notifications: who to reach, what they asked for, what we sent
-- ===========================================================================
-- Three tables, and the third is the one that matters most.
--
--   push_devices              where an alert can be delivered, and roughly
--                             where that device last was
--   notification_preferences  what each user agreed to be interrupted about
--   sent_alerts               every alert we actually sent — the rate cap, the
--                             per-flag debounce and the answer to "why did I
--                             get this?" all read from this one table
--
-- IMPLEMENTATION_PLAN.md S16 lists alert fatigue as a named risk from the
-- concept document (§12) and asks for "a documented rate cap per user per hour,
-- from day one, with a test". A cap is not a cap unless something durable
-- remembers what was already sent, so the ledger is part of the first migration
-- rather than a later addition. An in-memory counter would reset on every worker
-- restart, which on this project means every deploy.
--
-- All three are BACKEND-ONLY, like §5 of SCHEMA.sql: reached through
-- DATABASE_URL by SQLAlchemy, never through PostgREST. RLS is enabled with no
-- policies, so `anon` and `authenticated` cannot read or write them at all, and
-- the service role bypasses RLS. The app reaches them through
-- /api/v1/notifications/*, which is authenticated and scopes every query to the
-- caller.
--
-- That is a deliberate difference from `emergency_contacts` and `sos_hot_words`,
-- which the app edits directly through Supabase. A push token is a delivery
-- address: a client that could write the table could register a token against
-- another user's id and receive their alerts. Preferences are co-located with
-- the devices because a client that could edit preferences directly could also
-- raise its own rate cap, and the cap exists to protect the user from us.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 1. push_devices
-- ---------------------------------------------------------------------------
-- One row per install, not per user: someone with a phone and a tablet has two,
-- and both get alerted.
--
-- WARNING. `last_location` IS NOT A LOCATION HISTORY. It is a single point,
-- overwritten in place every time the app comes to the foreground and reports
-- where it is. There is no trace, no previous value and nothing to mine. That is
-- a privacy decision and also a scope decision: continuous background location
-- is S17, the other half of B6a, and it is not built. The honest consequence,
-- which the walkthrough and the preferences screen both state plainly, is that
-- an alert reaches someone based on where they were when they last opened the
-- app — so this cannot yet warn a person walking toward a flag with the app
-- closed.
--
-- `public.user_locations` is deliberately left unwritten. Appending a row per
-- update would create exactly the retention surface B14 has to govern, in
-- exchange for a history nothing reads.
create table if not exists public.push_devices (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users (id) on delete cascade,

    -- Expo's delivery address, `ExponentPushToken[...]`. Globally unique rather
    -- than unique per user: the token identifies an *install*, so if a phone is
    -- handed to someone else and they sign in, the row must move to the new
    -- owner instead of existing twice and delivering alerts to both. The
    -- registration endpoint upserts on this column and overwrites user_id.
    expo_push_token  text not null unique,

    platform         text not null,
    app_version      text,

    -- Last foreground position. Null until the app first reports one, which is
    -- normal: permission may be denied, and a device with no location simply
    -- never matches a corridor alert.
    last_location    extensions.geography(Point, 4326),
    last_location_at timestamptz,

    -- Set when Expo answers `DeviceNotRegistered` — the app was uninstalled or
    -- the token rotated. Soft-deleted rather than removed so `sent_alerts` keeps
    -- pointing at something real, and so a token that comes back (a reinstall
    -- re-registering) is reactivated by the same upsert.
    disabled_at      timestamptz,
    disabled_reason  text,

    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),

    constraint push_devices_platform_check
        check (platform in ('android', 'ios')),

    -- A position without the time it was taken is unusable: staleness is the
    -- whole basis on which the dispatcher decides whether to trust it.
    constraint push_devices_location_has_a_time
        check ((last_location is null) = (last_location_at is null))
);

comment on table public.push_devices is
    'One row per app install. last_location is a SINGLE overwritten point from '
    'the foreground, not a track — background location is S17 and is not built.';

create index if not exists idx_push_devices_user_id
    on public.push_devices (user_id);

-- The dispatcher's driving query: every live device that has told us where it
-- is. Partial, because disabled rows accumulate and are never dispatched to.
create index if not exists idx_push_devices_active_location
    on public.push_devices using gist (last_location)
    where disabled_at is null;


-- ---------------------------------------------------------------------------
-- 2. notification_preferences
-- ---------------------------------------------------------------------------
-- S16: "per-category user preferences". One row per user, created on demand —
-- an absent row means the defaults below, so someone who never opens the screen
-- is not excluded from alerts and nothing has to be back-filled.
--
-- The defaults ARE the alert-fatigue policy, so each one is argued.
create table if not exists public.notification_preferences (
    user_id          uuid primary key references auth.users (id) on delete cascade,

    -- Something is happening now, near where you are. The product's core
    -- promise, so on by default.
    corridor_alerts  boolean not null default true,

    -- D09's forward-dated windows: a road that will be blocked later today. On
    -- by default — it is actionable precisely because it arrives early.
    scheduled_alerts boolean not null default true,

    -- OFF by default, and this is the single most important line in the file.
    --
    -- A chronic flag is D02's police-statistics baseline: a historical average
    -- with a 2 km radius. Dhaka is covered in them, they do not move, and they
    -- never expire. Alerting on one means pushing "this area has a history"
    -- every time someone leaves the house, which is both useless and exactly
    -- the "stale red zones" behaviour demo beat 5 exists to disclaim. Chronic
    -- risk belongs on the map and in route scoring at 0.35 weight, not in a
    -- notification.
    chronic_alerts   boolean not null default false,

    -- Do not interrupt for less than this, on the 0-100 severity scale, after
    -- decay and after the confidence damping an unconfirmed flag gets. 40 is the
    -- bottom of the "moderate" band: below it the honest message is "you may
    -- lose a few minutes", which does not justify a notification.
    min_severity     double precision not null default 40,

    -- Local Dhaka hours, inclusive start, exclusive end, allowed to wrap
    -- (22 -> 7 is a night). Null means no quiet hours. Both null or both set.
    quiet_hours_start smallint,
    quiet_hours_end   smallint,

    -- A user may make themselves quieter than the system default
    -- (MAX_ALERTS_PER_USER_PER_HOUR) but not louder; the dispatcher takes the
    -- min of the two, so a value above the setting has no effect. Null = use
    -- the setting.
    max_per_hour     smallint,

    updated_at       timestamptz not null default now(),

    constraint notification_preferences_min_severity_range
        check (min_severity >= 0 and min_severity <= 100),
    constraint notification_preferences_quiet_hours_pair
        check ((quiet_hours_start is null) = (quiet_hours_end is null)),
    constraint notification_preferences_quiet_hours_range
        check (
            quiet_hours_start is null
            or (quiet_hours_start between 0 and 23 and quiet_hours_end between 0 and 23)
        ),
    constraint notification_preferences_max_per_hour_positive
        check (max_per_hour is null or max_per_hour > 0)
);

comment on table public.notification_preferences is
    'Per-category alert preferences. An absent row means the column defaults, '
    'which are themselves the alert-fatigue policy — chronic_alerts is off.';


-- ---------------------------------------------------------------------------
-- 3. sent_alerts
-- ---------------------------------------------------------------------------
-- The ledger. Three jobs, and it is worth being explicit that they are three,
-- because each one would otherwise be solved separately and inconsistently:
--
--   1. the hourly rate cap      count rows for this user since now - 1h
--   2. the per-flag debounce    the unique constraint below
--   3. "why did I get this?"    GET /notifications/history reads it back
--
-- Written BEFORE the send is attempted, then updated with the outcome. That
-- ordering is deliberate: if the Expo request times out having actually
-- delivered, a ledger written afterwards would lose the row and the next sweep
-- would send again. Over-counting a failed send against the cap is the cheaper
-- error than double-notifying someone — and `delivery` records which happened,
-- so nothing is hidden.
create table if not exists public.sent_alerts (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users (id) on delete cascade,

    -- No FK to risk_flags, on purpose, and the reason is the `test` category.
    --
    -- A test alert has no flag: it exists so the walkthrough can prove delivery
    -- without waiting for the city to produce an incident. It still needs a
    -- ledger row, because a test must count against the rate cap like anything
    -- else — otherwise the cap has a hole shaped like a debug endpoint. So it
    -- carries a freshly generated uuid that references nothing, which an FK
    -- would reject.
    --
    -- The integrity this gives up is small: a deleted flag leaves a history row
    -- whose statement is already stored in `title`/`body`, and nothing joins
    -- back to risk_flags to render it.
    flag_id          uuid not null,

    -- Which device it went to. `set null` rather than cascade: when a device is
    -- deleted the fact that the user was alerted is still true, and the rate cap
    -- must keep counting it.
    device_id        uuid references public.push_devices (id) on delete set null,

    category         text not null,

    -- Severity at the instant we decided to send, so the history can explain why
    -- this cleared min_severity when the flag has since decayed below it.
    severity_at_send double precision not null,

    -- What the user was actually shown. Stored rather than re-derived: the flag
    -- decays, Rumour Guard may confirm it later, and the history has to show the
    -- alert as sent, not as it would read today.
    title            text not null,
    body             text not null,

    delivery         text not null default 'queued',
    expo_receipt_id  text,
    error            text,

    sent_at          timestamptz not null default now(),

    constraint sent_alerts_category_check
        check (category in ('corridor', 'scheduled', 'chronic', 'test')),
    constraint sent_alerts_delivery_check
        check (delivery in ('queued', 'accepted', 'rejected')),

    -- S17's "no repeat for the same flag", enforced here rather than in the
    -- dispatcher's head. One alert per user per flag, ever — a flag that decays
    -- and re-intensifies does not get to interrupt twice, and a sweep running
    -- every minute cannot re-send what the previous sweep already sent.
    --
    -- `test` rows are naturally exempt: each one invents a new flag_id.
    constraint sent_alerts_one_per_user_per_flag
        unique (user_id, flag_id)
);

comment on table public.sent_alerts is
    'Every alert sent. Serves the hourly rate cap, the one-alert-per-flag '
    'debounce (unique constraint) and the user-visible alert history. Written '
    'before the send is attempted, so a lost response cannot cause a resend.';

comment on column public.sent_alerts.flag_id is
    'The risk flag this alert was about. Intentionally NOT a foreign key: test '
    'alerts carry a generated uuid referencing nothing so that they still count '
    'against the rate cap.';

-- The rate-cap query, run once per candidate alert: rows for one user inside a
-- one-hour window. Leading user_id, descending time.
create index if not exists idx_sent_alerts_user_recent
    on public.sent_alerts (user_id, sent_at desc);

create index if not exists idx_sent_alerts_flag_id
    on public.sent_alerts (flag_id);


-- ---------------------------------------------------------------------------
-- 4. updated_at triggers
-- ---------------------------------------------------------------------------
-- public.set_updated_at() is defined in SCHEMA.sql §6.
drop trigger if exists trg_push_devices_updated_at on public.push_devices;
create trigger trg_push_devices_updated_at
    before update on public.push_devices
    for each row execute function public.set_updated_at();

drop trigger if exists trg_notification_preferences_updated_at
    on public.notification_preferences;
create trigger trg_notification_preferences_updated_at
    before update on public.notification_preferences
    for each row execute function public.set_updated_at();


-- ---------------------------------------------------------------------------
-- 5. RLS: on, with no policies
-- ---------------------------------------------------------------------------
-- Same posture as SCHEMA.sql §5. Enabling RLS without policies denies the anon
-- and authenticated roles everything; the service role the backend uses bypasses
-- it. Without this, PostgREST would expose all three tables to any signed-in
-- user — including other people's push tokens.
alter table public.push_devices             enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.sent_alerts              enable row level security;
