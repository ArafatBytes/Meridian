-- ===========================================================================
-- D05 — when did we decide to believe this?
-- ===========================================================================
-- Rumour Guard promotes a flag from `unconfirmed` to `confirmed` the moment a
-- second independent publisher reports the same event. `confirmed_at` records
-- when that happened.
--
-- It is a claim about *our own process*, not about the event: `observed_at` is
-- when the city had the fire, `confirmed_at` is when we were willing to say so.
-- Demo beat 2 asks for exactly that distinction — "three independent sources,
-- confirmed 14:31" — and without this column the sheet can only say "confirmed"
-- with no answer to "when".
--
-- Nullable, and null for three legitimate reasons:
--   * the flag is still unconfirmed, which is most of them;
--   * it was authored confirmed in a fixture, so there was no moment of
--     promotion to record;
--   * it predates this migration. Backfilling it with `now()` would be
--     inventing a timestamp, and backfilling with `observed_at` would claim we
--     confirmed the event the instant it happened. Null is the honest value for
--     "we do not know", and the sheet renders it as such.
--
-- No CHECK tying confirmed_at to status. The temptation is
-- `status <> 'confirmed' or confirmed_at is not null`, and it would be wrong:
-- the 31 confirmed flags already in the fixture have no promotion moment, so the
-- constraint would make a valid seed unloadable. The invariant that matters
-- (`confirmed` requires two sources) is already enforced and is untouched here.
-- ===========================================================================

alter table public.risk_flags
    add column if not exists confirmed_at timestamptz;

comment on column public.risk_flags.confirmed_at is
    'When Rumour Guard promoted this flag to confirmed (D05). Null while '
    'unconfirmed, null for fixture flags authored confirmed, and null for rows '
    'that predate the column. Never back-filled: an invented confirmation time '
    'is worse than an absent one.';


-- Rumour Guard''s candidate lookup filters on (kind, status) before it does any
-- spatial or embedding work, and it runs once per extracted incident on a
-- 15-minute cadence. Both columns are low-cardinality, so this earns its keep by
-- keeping the candidate scan off the heap rather than by being selective.
create index if not exists idx_risk_flags_kind_status
    on public.risk_flags (kind, status);
