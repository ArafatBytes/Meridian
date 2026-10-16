"""
Invariant: **a journey has three states, and the database agrees.**

JG1 is the first phase of Journey Guardian and it is deliberately the dullest:
one row, three states, no clock. The thing worth pinning is not the behaviour --
there is barely any -- but the *agreement* between the three places the state
machine is written down, because JG2 and JG3 both add states and each will have
to add them in all three:

1. `app/models/journey.py` -- `STATES`, `TRANSITIONS`, `may_transition`.
2. The `journeys_state_check` CHECK, read out of the migration. The database
   will not store a state nobody declared.
3. `app/api/v1/endpoints/journeys.py` -- which has to consult `may_transition`
   rather than reimplementing it.

A phase that adds `check_in_sent` to the Python and forgets the CHECK gets a
failed insert in front of a judge; one that adds it to the CHECK and forgets the
Python gets a state the transition table has no edges for, which silently makes
every escalation step a 409. Both are the kind of bug a source-agreement test
catches in a second and a code review does not.

The other invariant here is the one that will matter most later:
**`journeys_ended_iff_terminal`**. A journey reading `arrived` with no instant of
arrival leaves nothing to say whether the deadline was met, and from JG2 onward
that question is the feature.
"""

import re
from pathlib import Path

import pytest

from app.models.journey import (
    PROFILES,
    STATE_ACTIVE,
    STATE_ARRIVED,
    STATE_CANCELLED,
    STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    may_transition,
)
from app.schemas.journey import JourneyStart

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
MIGRATION = BACKEND / "migrations" / "versions" / "20261014150000__journeys.sql"
ENDPOINT = BACKEND / "app" / "api" / "v1" / "endpoints" / "journeys.py"


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _sql_statements() -> str:
    """
    The migration with its prose removed: `--` comments and `comment on`
    statements stripped.

    Needed because this file asserts the *absence* of certain columns, and the
    migration explains at length which later phase each of them belongs to. A
    substring search over the whole file would find the explanation and call it
    the column.
    """
    sql = re.sub(r"--[^\n]*", "", _sql())
    return re.sub(r"comment on [^;]*;", "", sql, flags=re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# The state machine itself
# ---------------------------------------------------------------------------


def test_three_states_and_no_more():
    assert STATES == (STATE_ACTIVE, STATE_ARRIVED, STATE_CANCELLED)


def test_every_state_has_a_transition_entry():
    """A state with no entry in `TRANSITIONS` has no edges, which is a silent 409."""
    assert set(TRANSITIONS) == set(STATES)


def test_only_active_leads_anywhere():
    assert may_transition(STATE_ACTIVE, STATE_ARRIVED)
    assert may_transition(STATE_ACTIVE, STATE_CANCELLED)


def test_terminal_states_are_terminal():
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == ()
        for target in STATES:
            assert not may_transition(state, target), f"{state} -> {target}"


def test_a_journey_cannot_be_restarted():
    """
    Resuming is not a transition. The app's Resume button re-routes and keeps
    following the *same* active journey; a cancelled or arrived journey is
    finished, and going somewhere again means a new row -- which is what keeps
    `started_at` meaning what it says.
    """
    assert not may_transition(STATE_ARRIVED, STATE_ACTIVE)
    assert not may_transition(STATE_CANCELLED, STATE_ACTIVE)


def test_unknown_states_have_no_edges():
    assert not may_transition("check_in_sent", STATE_ARRIVED)
    assert not may_transition(STATE_ACTIVE, "full_sos")


# ---------------------------------------------------------------------------
# The database says the same thing
# ---------------------------------------------------------------------------


def test_migration_exists():
    assert MIGRATION.is_file(), f"{MIGRATION} is missing"


def test_state_check_lists_exactly_the_python_states():
    sql = _sql()
    match = re.search(
        r"constraint journeys_state_check\s*check \(state in \(([^)]*)\)\)",
        sql,
        re.IGNORECASE,
    )
    assert match, "journeys_state_check not found in the migration"
    in_sql = tuple(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert in_sql == STATES, f"SQL says {in_sql}, Python says {STATES}"


def test_profile_check_lists_exactly_the_python_profiles():
    sql = _sql()
    match = re.search(
        r"constraint journeys_profile_check\s*check \(route_profile in \(([^)]*)\)\)",
        sql,
        re.IGNORECASE,
    )
    assert match, "journeys_profile_check not found in the migration"
    assert tuple(re.findall(r"'([a-z_]+)'", match.group(1))) == PROFILES


def test_ended_at_exists_exactly_when_the_journey_has_ended():
    """
    `(state = 'active') = (ended_at is null)`. The shape of
    `gd_drafts_approved_iff_ready`: a state that cannot be faked by writing one
    column.
    """
    sql = _sql()
    assert "constraint journeys_ended_iff_terminal" in sql
    assert re.search(
        r"check \(\(state = 'active'\) = \(ended_at is null\)\)", sql, re.IGNORECASE
    ), "journeys_ended_iff_terminal is not the biconditional it claims to be"


def test_one_active_journey_per_user_is_enforced_by_a_partial_unique_index():
    """
    Not by the endpoint remembering to cancel the old one. Two live journeys
    means, from JG3 onward, two deadlines and two guardians watching one person.
    """
    sql = _sql()
    assert re.search(
        r"create unique index[^;]*on public\.journeys \(user_id\)\s*where state = 'active'",
        sql,
        re.IGNORECASE,
    ), "the partial unique index on one active journey per user is missing"


def test_user_id_points_at_auth_users():
    """
    `public.users` is a mirror that is not reliably populated;
    `20261010160000__gd_profiles_on_auth_users.sql` exists only because D08
    pointed at it. Every user-owned table added since points at `auth.users`.
    """
    sql = _sql()
    assert re.search(r"user_id\s+uuid not null references auth\.users \(id\)", sql, re.IGNORECASE)


def test_rls_is_on_with_no_policies():
    """
    Backend-only, like every table since B6a. A client that could write this
    table directly could start a journey against another user's id -- and from
    JG3 onward a journey is what decides whose guardian gets told something.
    """
    sql = _sql()
    assert "alter table public.journeys enable row level security;" in sql
    assert "create policy" not in sql.lower()


# ---------------------------------------------------------------------------
# JG1 has no clock, and the absence is the claim
# ---------------------------------------------------------------------------


def test_no_deadline_or_escalation_columns_yet():
    """
    JOURNEY_GUARDIAN.md on this phase: "Nothing watches anything yet. No
    deadline, no check-in, no escalation."

    A column with no clock behind it reads, to the next person, like a feature
    that exists. JG2 adds its own; this asserts JG1 did not guess them. Delete
    the relevant line here in the phase that actually builds the thing.
    """
    sql = _sql_statements().lower()
    for column in ("deadline", "check_in", "checkin", "escalat", "guardian_id"):
        assert column not in sql, f"'{column}' belongs to a later phase than JG1"


def test_the_migration_refuses_a_table_it_did_not_create():
    """
    `create table if not exists` is a silent no-op, and a `journeys` built by
    anything else has none of the constraints above -- so the invariant tests
    would pass while the database enforced nothing.

    The guard is what turns that silent skip into a stop. `journeys_state_check`
    is the sentinel because nothing but this migration creates it.
    """
    sql = _sql()
    guard = sql[: sql.index("create table if not exists public.journeys")]
    assert "raise exception" in guard, "the migration does not guard its own CREATE"
    assert "journeys_state_check" in guard


def test_journeys_is_not_an_orm_model():
    """
    The other half of the same fix, and the reason it is needed.

    `app/core/database.py::init_db` runs `Base.metadata.create_all` on every
    application start. For as long as JG1 had a `Journey(Base)` class, the
    running development server built the table from the *model* -- varchar
    instead of text, no CHECKs, no foreign key, no partial unique index, RLS off
    -- and the migration's `if not exists` then skipped it.

    Nothing reads this table through the ORM in any case: `origin` and
    `destination` are PostGIS geographies, and every read in this project that
    wants a latitude and a longitude does `ST_Y`/`ST_X` in the query. So the
    class bought nothing and cost the invariants.

    If a later phase genuinely needs the ORM here, it has to make `create_all`
    stop creating this table first -- not delete this test.
    """
    # `app.main` rather than `app.models`, because `create_all` sees whatever the
    # application has imported by the time it starts -- which is everything the
    # app module pulls in, including every endpoint.
    import app.main  # noqa: F401
    from app.core.database import Base

    assert "journeys" not in Base.metadata.tables, (
        "journeys is registered on Base, so init_db() will create it without "
        "constraints before the migration gets the chance"
    )


def test_no_position_log():
    """
    "A log written from day one is a privacy surface with no feature behind it
    yet." JG5 is the phase that wants history.
    """
    sql = _sql_statements().lower()
    assert "journey_positions" not in sql
    assert "create table" in sql
    assert sql.count("create table") == 1, "JG1 is one table"


# ---------------------------------------------------------------------------
# The endpoint does not reimplement the machine
# ---------------------------------------------------------------------------


def test_the_endpoint_consults_may_transition():
    """
    Rather than hardcoding which states may become which. The one definition has
    to be the one that decides, or JG2's new states will be legal in the model
    and rejected at the route.
    """
    source = ENDPOINT.read_text(encoding="utf-8")
    assert "may_transition" in source


def test_the_endpoint_derives_the_eta_server_side():
    """
    `eta_at` is `now() + duration`, computed in the INSERT. A deadline the
    client sets is a deadline the client can move, and from JG2 onward that
    deadline is the whole feature.
    """
    source = ENDPOINT.read_text(encoding="utf-8")
    assert "now() + make_interval(secs => :duration_seconds)" in source


def test_the_client_cannot_send_an_eta():
    """The other half of the above: there is no field for it to arrive in."""
    assert "eta_at" not in JourneyStart.model_fields
    assert "started_at" not in JourneyStart.model_fields
    assert "state" not in JourneyStart.model_fields
