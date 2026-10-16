"""
A journey, and the three states it can be in. JG1, the first phase of Journey
Guardian.

    active ──> arrived        the person got there
           └─> cancelled      they stopped it, or started another one

There is no `check_in_sent`, no `contacts_notified` and no `full_sos`. Those are
JG2 and JG3, and each adds its own state in its own migration. A state constant
with no code behind it reads, to the next person, like a feature that exists.

The database carries the same three in `journeys_state_check`, so the rule
survives anything that writes to the table -- including an endpoint nobody has
written yet. `tests/invariants/test_journey_states.py` pins the two lists
together.

Why there is no SQLAlchemy model in this file
---------------------------------------------
Every other table in `app/models/` has a `Base` subclass, and this one
deliberately does not. Two reasons, and the second is not a preference.

**Nothing would use it.** `origin` and `destination` are PostGIS geographies, and
reading one through the ORM hands back WKB that then needs decoding -- so every
read in this project that wants a latitude and a longitude does `ST_Y`/`ST_X` in
the query instead. `endpoints/journeys.py` is raw SQL throughout for that reason,
which leaves a model class with no caller.

**And declaring one would have created the table.** `app/core/database.py`'s
`init_db()` runs `Base.metadata.create_all` on every application start. A model
registered on `Base` therefore gets a table built from *the model* -- varchar
instead of text, no CHECK constraints, no foreign key, no partial unique index
and RLS off -- and `create table if not exists` in the migration then silently
skips it. The result is the worst available outcome: the invariant tests pass,
because they read the migration file, while the database enforces none of it.

That happened, on a running development server, within a minute of this file
first declaring the class. The constraints on `journeys` are the state machine;
they are not decoration, and the one way to be sure they exist is for the
migration to be the only thing that can create the table.
"""
from __future__ import annotations

STATE_ACTIVE = "active"
STATE_ARRIVED = "arrived"
STATE_CANCELLED = "cancelled"

#: Every state a journey may hold, in the order it can reach them. Mirrors
#: `journeys_state_check`.
STATES = (STATE_ACTIVE, STATE_ARRIVED, STATE_CANCELLED)

#: The states from which nothing further happens.
TERMINAL_STATES = (STATE_ARRIVED, STATE_CANCELLED)

#: The only transitions. A journey cannot un-arrive, and a cancelled journey is
#: not resumed -- resuming means continuing the one that is still active, which
#: is what keeps `started_at` meaning what it says.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    STATE_ACTIVE: (STATE_ARRIVED, STATE_CANCELLED),
    STATE_ARRIVED: (),
    STATE_CANCELLED: (),
}

#: The travel profiles a journey can be made on. Mirrors
#: `journeys_profile_check`, and the same two the route planner offers.
PROFILES = ("driving", "foot")


# ---------------------------------------------------------------------------
# How worried we are about it. JG2.
# ---------------------------------------------------------------------------
# A second axis, not more values on `state`.
#
# A journey being asked a question is still active -- it has not arrived and it
# has not been cancelled. Folding the two together would mean every query that
# asks "is this journey running" has to know the escalation vocabulary, and
# would make the escalation chain JG3 builds into a set of extra ways for a
# journey to be over. `state` is where the journey is; `escalation_state` is how
# worried we are about it.

ESCALATION_NORMAL = "normal"
ESCALATION_CHECK_IN_SENT = "check_in_sent"
ESCALATION_CHECK_IN_REPEATED = "check_in_repeated"
ESCALATION_CONTACTS_NOTIFIED = "contacts_notified"
ESCALATION_FULL_SOS = "full_sos"

#: Every escalation state. Mirrors `journeys_escalation_check`.
#:
#: Ordered, and the order is the escalation: each name widens the circle by
#: exactly one ring. `ESCALATION_LADDER` below depends on that, and a state
#: inserted in the wrong place here would silently reorder the chain.
ESCALATION_STATES = (
    ESCALATION_NORMAL,
    ESCALATION_CHECK_IN_SENT,
    ESCALATION_CHECK_IN_REPEATED,
    ESCALATION_CONTACTS_NOTIFIED,
    ESCALATION_FULL_SOS,
)

#: The escalation path, in order, excluding `normal`.
#:
#: Derived from `ESCALATION_STATES` rather than written out again: two lists of
#: the same thing are two lists free to disagree, and the disagreement here
#: would be a skipped ring.
ESCALATION_LADDER = ESCALATION_STATES[1:]

#: Every escalation edge. Mirrors the CHECKs in
#: `20261015180000__journey_guardian.sql`.
#:
#: Two kinds of edge, and the asymmetry is the design:
#:
#: * **One step forward**, never two. `JOURNEY_GUARDIAN.md` §7 -- *"escalate in
#:   steps, and never skip one"* -- and the migration enforces it with three
#:   ordering CHECKs so a bug here is an IntegrityError rather than an email to
#:   somebody's mother.
#: * **Back to `normal` from anywhere.** Answering ends it, whatever ring the
#:   journey had reached, which is what "the trip goes quiet again" means. It
#:   makes the machine a cycle, so a journey that runs long is asked again --
#:   deliberate, and a terminal state would mean one question per journey.
ESCALATION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    ESCALATION_NORMAL: (ESCALATION_CHECK_IN_SENT,),
    ESCALATION_CHECK_IN_SENT: (ESCALATION_NORMAL, ESCALATION_CHECK_IN_REPEATED),
    ESCALATION_CHECK_IN_REPEATED: (ESCALATION_NORMAL, ESCALATION_CONTACTS_NOTIFIED),
    ESCALATION_CONTACTS_NOTIFIED: (ESCALATION_NORMAL, ESCALATION_FULL_SOS),
    #: Terminal except for an answer. There is no sixth ring in this product:
    #: JG7's witnesses are fired by a *confirmed* emergency, never by an
    #: unanswered check-in, so they are not an edge out of here.
    ESCALATION_FULL_SOS: (ESCALATION_NORMAL,),
}

#: The timestamp column that records each escalation step, by state.
#:
#: The sweep gates every forward step on the *previous* state's column, so this
#: mapping is what makes "no step without a recorded non-response" expressible
#: in one place instead of repeated in three SQL statements.
ESCALATION_RECORDED_AT: dict[str, str] = {
    ESCALATION_CHECK_IN_SENT: "check_in_sent_at",
    ESCALATION_CHECK_IN_REPEATED: "check_in_repeated_at",
    ESCALATION_CONTACTS_NOTIFIED: "contacts_notified_at",
    ESCALATION_FULL_SOS: "full_sos_at",
}


def next_escalation(current: str) -> str | None:
    """
    The one state `current` may escalate to, or None at the end of the ladder.

    Reads `ESCALATION_TRANSITIONS` rather than indexing the ladder, so a state
    whose edges are later restricted cannot be escalated past by this helper
    while still looking reachable in the table.
    """
    for target in ESCALATION_TRANSITIONS.get(current, ()):
        if target != ESCALATION_NORMAL:
            return target
    return None


def may_transition(current: str, target: str) -> bool:
    """Whether `current -> target` is an edge. Unknown states have no edges."""
    return target in TRANSITIONS.get(current, ())


def may_escalate(current: str, target: str) -> bool:
    """
    Whether `current -> target` is an escalation edge. Unknown states have none.

    Deliberately the same shape as `may_transition` rather than one function
    taking a machine, because the two machines are read by different code and
    JG3 changes only one of them.
    """
    return target in ESCALATION_TRANSITIONS.get(current, ())

