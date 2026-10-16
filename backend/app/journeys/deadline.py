"""
When we expect you, and what is allowed to move it. JG2.

Every number this phase has is here, and nothing here touches the database, the
clock or the network. That is the point of the module: JOURNEY_GUARDIAN.md's note
on JG2 says the grace period "is a guess until JG4 and the trial", and JG4's own
entry says the derivation must be "a pure function, so it can be tested without a
phone". This is that function's home, with constants standing in for it until the
risk score and the hour get a vote.

So **JG4 is a change to this file and to what its callers pass in.** It is not a
change to the sweep, the table or the app. If a later phase finds itself writing
a duration somewhere else, the mistake is there and not here.

## Offsets, not instants

Every function returns a `timedelta` from some reference point rather than a
`datetime`, and the endpoints turn them into instants with `now() +
make_interval(...)` in SQL.

That split is deliberate. The server's clock is the database's clock -- a journey
started by one worker and swept by another has to agree on what time it is, and
two processes reading their own `datetime.now()` do not. Keeping the arithmetic
here and the clock there means this module can be tested with no database and the
database never needs a number this module did not produce.

The two rules that are *not* arithmetic -- a heartbeat may only move the deadline
forward, and may never move it past the ceiling -- live in the endpoint's SQL,
because they are about the row's current value and have to be evaluated where the
row is to be safe against two heartbeats racing. `test_journey_deadline.py` reads
that SQL and asserts both are present.

## Why generous

> "Start generous -- a feature that cries wolf in week one never gets a week
> two."

The nightmare for this feature is not missing an emergency, it is calling
somebody's mother because she stopped for tea. Ten minutes on top of a route's
own ETA absorbs a Dhaka jam, a wrong turn and a stop at a tea stall, and still
notices a phone snatched at the halfway point inside half an hour.

Nothing about these five numbers is defended as correct. They are starting values,
they are in one place so the trial can move them, and the invariant test pins
`GRACE` to the migration's backfill so a change here cannot silently make old
journeys behave unlike new ones.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

__all__ = [
    "ANSWER_EXTENSION",
    "CHECK_IN_WINDOW",
    "GRACE",
    "MAX_DEADLINE",
    "MIN_DEADLINE",
    "heartbeat_offset",
    "leash",
    "start_offset",
]


GRACE: Final = timedelta(minutes=10)
"""
Added to the route's own ETA to get the default deadline, and added again to
every live estimate a heartbeat reports.

The router does not know she is stopping for food, and it does not know about the
jam that formed after the route was computed. Ten minutes is the allowance for
both. JG4 is where this stops being one number: an 11pm ride through flagged
corridors should not get the same allowance as a 2pm commute.
"""

CHECK_IN_WINDOW: Final = timedelta(minutes=1)
"""
How long a check-in waits for an answer before the non-response is recorded.

⚠️ **SHORTENED ON THIS BRANCH FOR FILMING: 5 minutes → 1 minute.**
`feature/test-v` exists to shoot the demo video. The real ladder is
deadline → buzz → *5 min* → buzz → *5 min* → guardian emailed, which is about
thirteen minutes of waiting and unfilmable in a 25-second segment. At one minute
the whole ladder runs in roughly four. **Do not merge this value.** The product
value is five minutes and the reasoning for it is below, unchanged.

The check-in is a liveness test first and a question second -- a phone that has
merely been in a coverage gap wakes on the push and answers in one tap, and Dhaka
has enough of those gaps that this is the common case. Five minutes is long enough
for a phone to come back and short enough that the recorded non-response still
means something.

Nothing happens when it elapses in JG2 beyond the record itself. JG3 escalates,
and is not allowed to escalate without that record.
"""

ANSWER_EXTENSION: Final = timedelta(minutes=15)
"""
How much time answering buys, measured from the answer.

Not "back to where it was", which is unbounded on a journey that is genuinely
running late, and not the full grace period, which would make tapping "I'm fine"
the cheapest way to be left alone for an hour. Fifteen minutes is one more leg of
a trip; somebody still going gets asked again, which is the behaviour a safety
feature should have.

Measured from the answer rather than from the deadline that just passed: a
journey asked an hour late would otherwise have its extension backdated into the
past and be instantly due again -- the feature asking twice in a row for no reason
the person can see.

**Capped by the leash, where there is one.** This number is a guess; a leash is
something the person said out loud. Fifteen minutes handed to somebody who asked
to be checked on every two is the same override `leash` exists to prevent, and
the `coalesce` in `_CHECK_IN` is the other half of the one in `_HEARTBEAT`. It
only bites the short leash -- `1 hr` and `30 min` are both longer than this, so
`least` leaves them at fifteen.
"""

MIN_DEADLINE: Final = timedelta(minutes=2)
"""
The shortest deadline a person may set at start.

Two minutes rather than zero so a deadline is always in the future when it is
written -- `journeys_deadline_after_start` rejects a past one -- and so the
walkthrough can be run without waiting out a real journey. It is also a real case
and not only a test affordance: "ask me in two minutes" is what somebody walking
the last stretch home wants, and it is JG6's short leash arriving early.
"""

MAX_DEADLINE: Final = timedelta(hours=6)
"""
The longest deadline a person may set, and the ceiling a heartbeat may slide to.

Without a ceiling, a phone reporting a steady "about twenty minutes left" from
inside a bag extends its own deadline forever, one minute at a time, and the
journey never becomes due. That is the one way silence can be laundered into an
extension. It is closed with a ceiling rather than by trying to detect movement,
because movement detection needs signals this phase does not collect -- that is
JG5, and guessing at it here would produce a check-in that fires in a traffic jam,
which is the exact false alarm JOURNEY_GUARDIAN.md §1 warns the whole design
against.

Six hours is past any journey inside Dhaka and short enough that a forgotten
journey resolves itself the same day.
"""


def start_offset(
    *,
    duration_minutes: float,
    chosen_minutes: int | None = None,
) -> timedelta:
    """
    How long after `started_at` the first deadline falls.

    `chosen_minutes` is what the person picked at start. `None` means they
    accepted the default, which is the route's own ETA plus `GRACE`.

    Clamped at both ends, and the clamp applies to the default as much as to a
    choice: a six-hour route would otherwise write a deadline the sweep does not
    reach until tomorrow, and a zero-minute route -- which the router will
    cheerfully return for a destination across the street -- would write one in
    the past and be rejected by the CHECK.
    """
    chosen = leash(chosen_minutes=chosen_minutes)
    if chosen is not None:
        return chosen
    return _clamp(timedelta(minutes=duration_minutes) + GRACE)


def leash(*, chosen_minutes: int | None) -> timedelta | None:
    """
    The longest this journey may go unheard-from, when the person said so.

    `None` when they accepted the route's own ETA, which means "derive it from
    what is left of the route" rather than "no limit" -- the heartbeat does that
    derivation.

    ## Why this has to be stored rather than recomputed

    Somebody who picks "2 min" is making a statement about how long they are
    willing to be unwatched, not about this particular leg of the route. Without
    it the first heartbeat would move their deadline to `now + remaining +
    GRACE` and hand them ten minutes they did not ask for -- which is exactly
    what happened the first time this phase was run on a phone: a two-minute
    leash became a twelve-minute one sixty seconds later, silently, and the
    check-in never came.

    The original choice cannot be recovered from the row afterwards, because
    `deadline_at - started_at` is the one thing heartbeats overwrite. So it is a
    column.
    """
    if chosen_minutes is None:
        return None
    return _clamp(timedelta(minutes=chosen_minutes))


def heartbeat_offset(*, remaining_seconds: float) -> timedelta:
    """
    How far past *now* a heartbeat proposes to put the deadline.

    The phone's own live estimate plus `GRACE`. `remaining_seconds` comes from
    the navigator (`remainingSeconds` in `useNavigation`), which measures GPS
    progress rather than replaying the route's original promise -- which is what
    lets a jam extend the deadline honestly: the phone says "still going, longer
    than I thought", and the clock follows.

    This is a *proposal*, and it is capped by the leash. Whether it is taken is
    decided in SQL, where the row's current deadline and its leash are:

        deadline = greatest(deadline, now + least(this, leash))   -- capped

    all three parts of which matter.

    **`greatest`** means forward only. A phone that could pull its own deadline
    in could be made to pull it to the next second by anything holding the
    session, and the difference between "asked a bit early" and "a deadline
    somebody else set for you" is the difference between a nuisance and a weapon.

    **`least(this, leash)`** is what stops a heartbeat overriding an explicit
    choice. Somebody who asked to be checked on in two minutes must not be handed
    ten by their own phone reporting in -- see `leash`. With no leash the cap is
    absent and this proposal stands, which is the default behaviour.

    **The cap** is `started_at + MAX_DEADLINE`.
    """
    return timedelta(seconds=max(0.0, remaining_seconds)) + GRACE


def _clamp(offset: timedelta) -> timedelta:
    """
    `[MIN_DEADLINE, MAX_DEADLINE]`, applied to every offset this module returns.

    One function rather than the expression twice, because `start_offset` and
    `leash` have to agree exactly: they are the same choice written to two
    columns, and a clamp that differed between them would let the first heartbeat
    move the deadline somewhere the initial one was not allowed to be.
    """
    return max(MIN_DEADLINE, min(offset, MAX_DEADLINE))
