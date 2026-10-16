"""
Invariant: **silence never extends a deadline, and nobody is told anything yet.**

JG2 gives a journey a clock and one question. Two claims are worth pinning, and
they are the two that would be invisible if they broke.

**The first is an absence.** The design's whole asymmetry is that a phone in a
jam talks and a phone in a ditch does not, so the deadline must move only when
something asks it to. There is no test that can prove no future code path extends
a deadline; what these tests do instead is pin the three properties that make the
one existing path safe -- it moves the deadline forward only, never past a
ceiling, and never at all once a question is outstanding -- and assert that the
sweep sends nothing on its second branch.

**The second is a cross-codebase contract.** Three strings have to be spelled
identically in Python and TypeScript, with nothing at build time to check them,
and each fails silently in its own way:

    journey_check_in (channel)   Android files the notification under a fallback
                                 with default importance and no sound
    journey_check_in (category)  the notification arrives with NO BUTTONS, and
                                 the one-tap answer becomes "open the app"
    GRACE = 10 minutes           the planner promises 10:40 and the server asks
                                 at 10:55

The same crude approach as `test_alert_channels_match_the_client.py`, for the
same reason given there: it is this or nothing.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.journeys.checkin import (
    CHECK_IN_ACTION_CATEGORY,
    CHECK_IN_ACTION_OK,
    CHECK_IN_CHANNEL,
    compose_check_in,
)
from app.journeys.deadline import (
    ANSWER_EXTENSION,
    CHECK_IN_WINDOW,
    GRACE,
    MAX_DEADLINE,
    MIN_DEADLINE,
    heartbeat_offset,
    leash,
    start_offset,
)
from app.models.journey import (
    ESCALATION_CHECK_IN_SENT,
    ESCALATION_NORMAL,
    ESCALATION_STATES,
    ESCALATION_TRANSITIONS,
    may_escalate,
)

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
MIGRATION = BACKEND / "migrations" / "versions" / "20261015120000__journey_deadline.sql"
LEASH_MIGRATION = BACKEND / "migrations" / "versions" / "20261015140000__journey_leash.sql"
ENDPOINT = BACKEND / "app" / "api" / "v1" / "endpoints" / "journeys.py"
AGENT = BACKEND / "app" / "agents" / "journey_watch.py"

_CLIENT_CHECK_IN = Path("frontend") / "src" / "features" / "journey" / "checkIn.ts"
_CLIENT_DEADLINE = Path("frontend") / "src" / "features" / "journey" / "deadline.ts"
_CLIENT_CHANNELS = Path("frontend") / "src" / "features" / "alerts" / "channels.ts"


def _client(relative: Path) -> Path | None:
    """
    Locate a client file, or report that this environment has no frontend.

    Two environments run this suite -- the repository root and the backend
    container, which has no `frontend/` -- and the same two candidates
    `test_alert_channels_match_the_client.py` tries.
    """
    for root in (BACKEND.parent, BACKEND):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


needs_client = pytest.mark.skipif(
    _client(_CLIENT_CHECK_IN) is None,
    reason="no frontend tree here (backend container); checked at the repo root",
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _endpoint() -> str:
    return ENDPOINT.read_text(encoding="utf-8")


def _endpoint_sql() -> str:
    """
    Only the SQL in the endpoint module, with the Python around it dropped.

    Needed because `_response` builds a `JourneyResponse` with
    `deadline_at=row.deadline_at`, which a substring search for an assignment to
    `deadline_at` finds and counts as a write. That is the difference between a
    test that says "two statements may move a deadline" and one that says
    "something somewhere mentions the word".
    """
    return "\n".join(re.findall(r'text\(\s*f?"""(.*?)"""', _endpoint(), re.S))


# ---------------------------------------------------------------------------
# The escalation machine, and the database agreeing with it
# ---------------------------------------------------------------------------


def test_jg2s_two_states_are_still_the_first_two():
    """
    This was `test_two_escalation_states_and_no_more`, asserting the tuple had
    exactly two entries so JG2 could not guess at JG3's vocabulary. JG3 has now
    landed and added three, so the scope boundary it guarded is gone.

    What survives is the part that is still load-bearing: `normal` and
    `check_in_sent` are the *first two*, in that order. `ESCALATION_LADDER` is a
    slice of this tuple and the sweep escalates along it, so an insertion before
    `check_in_sent` would silently reorder the chain and put a ring before the
    first question.

    The five-state assertion lives in `test_journey_guardian.py`, next to the
    migration that now defines the CHECK.
    """
    assert ESCALATION_STATES[:2] == (ESCALATION_NORMAL, ESCALATION_CHECK_IN_SENT)


def test_answering_returns_the_journey_to_normal():
    """
    "The trip goes quiet again." A terminal `check_in_sent` would mean the
    question could only ever be asked once per journey.
    """
    assert may_escalate(ESCALATION_CHECK_IN_SENT, ESCALATION_NORMAL)
    assert may_escalate(ESCALATION_NORMAL, ESCALATION_CHECK_IN_SENT)


def test_every_escalation_state_has_a_transition_entry():
    assert set(ESCALATION_TRANSITIONS) == set(ESCALATION_STATES)


def test_unknown_escalation_states_have_no_edges():
    """
    `may_escalate` must refuse a name it does not know rather than raise, so a
    stale value read from the database cannot take the sweep down.

    The examples used to be `full_sos` and `contacts_notified`, which JG3 made
    real -- so they now test the opposite of what they were written for. Replaced
    with a name no phase will ever add.
    """
    assert not may_escalate("panic", ESCALATION_NORMAL)
    assert not may_escalate(ESCALATION_NORMAL, "panic")
    # And the one that matters: `normal` still cannot reach past the first ring.
    assert not may_escalate(ESCALATION_NORMAL, "contacts_notified")


def test_this_migration_created_the_escalation_check():
    """
    This used to assert the CHECK listed exactly `ESCALATION_STATES`. It cannot
    any more, and the reason is worth keeping: JG3's migration **replaces** this
    constraint with a five-name version, so a JG2 file comparing its own
    migration against today's Python tuple is comparing against a constraint
    that no longer exists in the database.

    So the equality moved to `test_journey_guardian.py`, beside the migration
    that currently defines it, and what is checked here is the narrower fact
    that remains true for ever: this migration is where the constraint was
    introduced, with the two states JG2 knew about.
    """
    match = re.search(
        r"check \(escalation_state in \(([^)]*)\)\)", _sql(), re.IGNORECASE
    )
    assert match, "journeys_escalation_check not found in the migration"
    in_sql = tuple(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert in_sql == (ESCALATION_NORMAL, ESCALATION_CHECK_IN_SENT)


def test_an_answer_requires_a_question():
    """
    `journeys_answered_after_asked`. Without it, an answer written onto a journey
    nobody asked about would buy an extension -- which is what a replayed
    notification action would be.
    """
    assert "journeys_answered_after_asked" in _sql()
    assert re.search(
        r"answered_at is null\s*or \(check_in_sent_at is not null and answered_at >= check_in_sent_at\)",
        _sql(),
        re.IGNORECASE,
    )


def test_a_non_response_requires_a_question():
    """
    `journeys_unanswered_after_asked`, and it matters more than the above: JG3
    escalates on `unanswered_at`, so a row carrying one with no question behind
    it would be an escalation with no recorded cause.
    """
    assert "journeys_unanswered_after_asked" in _sql()


def test_the_deadline_cannot_predate_the_journey():
    assert "journeys_deadline_after_start" in _sql()
    assert re.search(r"check \(deadline_at >= started_at\)", _sql(), re.IGNORECASE)


def test_the_migration_refuses_a_journeys_table_jg1_did_not_build():
    """
    Same guard, same reason as JG1's: `add column if not exists` is a silent
    no-op, and `Base.metadata.create_all` has built a constraint-free `journeys`
    from a model once already.
    """
    sql = _sql()
    guard = sql[: sql.index("alter table public.journeys")]
    assert "raise exception" in guard
    assert "journeys_state_check" in guard


# ---------------------------------------------------------------------------
# The clock, and the asymmetry that is the whole design
# ---------------------------------------------------------------------------


def test_the_default_deadline_is_the_route_eta_plus_grace():
    assert start_offset(duration_minutes=30) == timedelta(minutes=30) + GRACE


def test_a_chosen_deadline_is_taken_as_given():
    assert start_offset(duration_minutes=30, chosen_minutes=45) == timedelta(minutes=45)


def test_a_deadline_is_never_written_in_the_past():
    """
    The router returns zero minutes for a destination across the street, and
    `journeys_deadline_after_start` would reject the row. `MIN_DEADLINE` is what
    stops a legitimate short trip becoming a 500.
    """
    assert start_offset(duration_minutes=0) >= MIN_DEADLINE
    assert start_offset(duration_minutes=30, chosen_minutes=0) == MIN_DEADLINE


def test_the_clamp_applies_to_the_default_as_well_as_to_a_choice():
    """A ten-hour route must not write a deadline the sweep reaches tomorrow."""
    assert start_offset(duration_minutes=10 * 60) == MAX_DEADLINE
    assert start_offset(duration_minutes=1, chosen_minutes=10_000) == MAX_DEADLINE


def test_a_heartbeat_proposes_its_own_estimate_plus_grace():
    assert heartbeat_offset(remaining_seconds=600) == timedelta(seconds=600) + GRACE


def test_a_heartbeat_cannot_propose_a_negative_offset():
    assert heartbeat_offset(remaining_seconds=-5) == GRACE


def test_the_heartbeat_moves_the_deadline_forward_only():
    """
    `greatest(deadline_at, ...)`, evaluated against the row.

    A phone that could pull its own deadline in could be made to pull it to the
    next second by anything holding the session, and "a deadline somebody else
    set for you" is a different thing from "asked a bit early".
    """
    sql = _endpoint()
    heartbeat = sql[sql.index("_HEARTBEAT") : sql.index("_CHECK_IN")]
    # Split across lines since the leash cap went inside it, so the assertion is
    # on the two operands rather than on one formatted string.
    assert "greatest(" in heartbeat
    assert "deadline_at," in heartbeat
    assert "now() + make_interval(secs => least(" in heartbeat


def test_the_heartbeat_cannot_slide_past_the_ceiling():
    """
    Without it, a steady "about twenty minutes left" from a stationary phone
    extends its own deadline forever, one minute at a time, and the journey is
    never due. That is the one way silence can be laundered into an extension.
    """
    sql = _endpoint()
    heartbeat = sql[sql.index("_HEARTBEAT") : sql.index("_CHECK_IN")]
    assert "least(" in heartbeat
    assert "started_at + make_interval(secs => :ceiling_seconds)" in heartbeat


def test_a_heartbeat_does_not_move_a_deadline_once_a_question_is_outstanding():
    """
    A phone whose GPS is still ticking in a bag must not talk its way out of a
    question a person has to answer.
    """
    sql = _endpoint()
    heartbeat = sql[sql.index("_HEARTBEAT") : sql.index("_CHECK_IN")]
    assert re.search(r"when escalation_state = 'normal' then", heartbeat)
    assert "else deadline_at" in heartbeat


def test_an_answer_is_only_accepted_against_an_outstanding_question():
    """
    The rule JG2 wrote, with the state it named taken out of it.

    This asserted `escalation_state = 'check_in_sent'` -- the only state a
    question could be outstanding in when it was written. JG3 added three more,
    and that exact string then became a bug rather than an invariant: the
    endpoint refused an answer from a journey the sweep had already escalated,
    which is the journey whose owner is being pushed hardest to answer. See
    `test_journey_guardian.py::test_an_answer_is_accepted_from_every_rung_of_the_ladder`.

    What survives is the half this test was really for, and it is unchanged:
    there must be a question. An answer accepted on a journey in `normal` is a
    deadline extension bought by replaying a notification action.
    """
    sql = _endpoint()
    # To the end of the statement, not to the next name: `_SELECT_ONE` is
    # declared above `_CHECK_IN` in this module, so slicing to it ran backwards
    # and silently searched an empty string.
    check_in = sql[sql.index("_CHECK_IN") : sql.index("def _response")]
    assert "and escalation_state in ({_ANSWERABLE})" in check_in, (
        "the answer path no longer filters on escalation_state at all, so an "
        "answer out of nowhere would buy an extension"
    )
    from app.api.v1.endpoints.journeys import _ANSWERABLE

    assert "'normal'" not in _ANSWERABLE


def test_nothing_but_a_heartbeat_or_an_answer_writes_deadline_at():
    """
    The absence that is the feature.

    Three writes to `deadline_at` in the whole backend: the INSERT, the
    heartbeat, and the answer. A fourth would be a way for a deadline to move
    that nobody asked for, and the one in the sweep would be the worst of them --
    a journey that extended itself when it came due.
    """
    writers = re.findall(r"deadline_at\s*=", _endpoint_sql())
    assert len(writers) == 2, (
        f"{len(writers)} assignments to deadline_at in the endpoint; expected the "
        "heartbeat and the answer. A third means something else can move a "
        "deadline -- if that is deliberate, it needs its own test here."
    )
    # Reads are fine and necessary -- the sweep's whole job is `deadline_at <=
    # now`. What it must never do is assign to it. The regex distinguishes the
    # two: `\s*=` cannot bridge the `<` in `deadline_at <= :now`.
    assert not re.search(r"deadline_at\s*=", AGENT.read_text(encoding="utf-8")), (
        "the sweep assigns to deadline_at. The sweep is what notices a deadline "
        "has passed; a sweep that could move one could postpone the thing it "
        "exists to report."
    )


# ---------------------------------------------------------------------------
# The sweep notices, and tells nobody
# ---------------------------------------------------------------------------


def test_the_sweep_runs_every_minute():
    from app.agents.journey_watch import AGENT as agent

    assert agent.cron == "* * * * *"
    assert agent.name == "journey_watch"


def test_the_sweep_is_discovered_by_the_registry():
    """
    Adding an agent is one new module, never an edit to a central list -- so the
    way this one fails is by not being found at all, which nothing else notices.
    """
    from app.agents.registry import agents

    assert "journey_watch" in agents()


def test_recording_a_non_response_is_separate_from_acting_on_it():
    """
    This was `test_the_non_response_branch_sends_nothing`, and its docstring
    said: *"the moment the sweep can notify somebody about a non-response, JG2
    has become JG3"*. JG3 has arrived and the sweep now does exactly that, so
    that framing is spent -- `JG3_PLAN.md` predicted this test would be deleted.

    It is kept instead, because what it actually asserts turns out to be
    narrower and still true: **`_RECORD_NON_RESPONSE` itself writes a timestamp
    and nothing else.** The acting lives in separate statements
    (`_REPEAT_THE_QUESTION` and the two above it) with their own gates, and that
    separation is the reason the escalation can be reasoned about at all -- the
    record is made by one statement that cannot send, and consumed by others
    that cannot record.

    Folding a send into this statement would mean a non-response and the
    reaction to it became the same event, and "every step past the first
    requires a recorded non-response" would no longer be checkable by looking
    at a row.
    """
    source = AGENT.read_text(encoding="utf-8")
    record = source[source.index("_RECORD_NON_RESPONSE") : source.index("_DEVICES")]
    for forbidden in ("transport", "send(", "compose_", "contact", "guardian"):
        assert forbidden not in record, (
            f"the non-response branch mentions {forbidden!r}. Recording a "
            "non-response is JG2; telling anyone about it is JG3."
        )


def test_the_sweep_does_not_record_a_non_response_it_just_asked_about():
    """
    The cutoff is `now - CHECK_IN_WINDOW`, so a journey asked in this run cannot
    also be marked unanswered by it -- which would make every check-in an instant
    non-response and, in JG3, an instant escalation.
    """
    source = AGENT.read_text(encoding="utf-8")
    assert "ctx.now - CHECK_IN_WINDOW" in source
    assert "check_in_sent_at <= :cutoff" in source


def test_an_answer_to_a_previous_question_does_not_count():
    """
    A journey asked at 10:40, answered at 10:41 and asked again at 10:56 carries
    a real `answered_at` that is about the earlier question. Reading it alone
    would make the second question look answered the moment it was asked.
    """
    source = AGENT.read_text(encoding="utf-8")
    assert "answered_at is null or answered_at < check_in_sent_at" in source


def test_the_sweep_marks_the_journey_even_when_the_push_fails():
    """
    Otherwise a journey left at `normal` because Expo was down is swept again
    the next minute, and the one after -- buzzing the phone once a minute for the
    rest of the trip the moment delivery recovers. Worse, the clock never starts
    on the non-response, so a phone that is genuinely gone never produces the
    record JG3 escalates on.
    """
    source = AGENT.read_text(encoding="utf-8")
    ask = source[source.index("async def _ask") :]
    mark = ask.index("_MARK_SENT")
    send = ask.index("transport.send")
    assert mark < send, "the state is moved after the push, so a failed push repeats it"


# ---------------------------------------------------------------------------
# The check-in says nothing about where you are
# ---------------------------------------------------------------------------


def test_the_check_in_names_no_place_and_no_time():
    """
    JOURNEY_GUARDIAN.md §5: the dangerous case is the one where the person who
    put her in the car is watching her answer it. A notification naming her
    destination tells him where she is going; one naming her deadline tells him
    how long he has.
    """
    message = compose_check_in(journey_id="abc")
    text = f"{message.title} {message.body}".lower()
    for forbidden in ("mirpur", "destination", "arrive by", "deadline", "min", "km"):
        assert forbidden not in text, f"the check-in body says {forbidden!r}"


def test_the_journey_id_rides_in_data_and_not_in_the_text():
    message = compose_check_in(journey_id="journey-123")
    assert message.data["journeyId"] == "journey-123"
    assert "journey-123" not in message.title
    assert "journey-123" not in message.body


def test_the_check_in_is_not_a_risk_alert():
    """
    No `AlertCategory`, so it cannot be routed through `sent_alerts`, the hourly
    rate cap or `compose_alert`'s framing. A safety question a person misses
    because they had already read five traffic notifications is the feature
    working backwards.
    """
    message = compose_check_in(journey_id="abc")
    assert message.category is None
    assert message.channel_id == CHECK_IN_CHANNEL
    assert message.channel_id not in ("risk_alert", "sos_alert", "system")


def test_the_check_in_carries_its_action_category():
    """Without it the notification arrives with no buttons, silently."""
    assert compose_check_in(journey_id="abc").action_category == CHECK_IN_ACTION_CATEGORY


def test_the_transport_sends_the_action_category():
    expo = (BACKEND / "app" / "alerts" / "expo.py").read_text(encoding="utf-8")
    assert '"categoryId": message.action_category' in expo


def test_there_is_exactly_one_button():
    """
    JOURNEY_GUARDIAN.md §5 describes a second one that looks identical and
    silently escalates. That is JG6, and it needs JG3's chain before it can do
    anything but lie -- a decoy wired to the same endpoint as the real button
    would teach somebody to trust a control that does nothing.
    """
    checkin = (BACKEND / "app" / "journeys" / "checkin.py").read_text(encoding="utf-8")
    assert checkin.count("CHECK_IN_ACTION_") == checkin.count("CHECK_IN_ACTION_OK") + (
        checkin.count("CHECK_IN_ACTION_CATEGORY")
    ), "a second action id appeared in checkin.py; JG6 is the phase for that"


# ---------------------------------------------------------------------------
# The three strings the app has to spell the same way
# ---------------------------------------------------------------------------


@needs_client
def test_the_check_in_channel_exists_on_the_client():
    """
    `PushMessage.channel_id`'s explicit-channel branch is invisible to
    `test_alert_channels_match_the_client.py`, which reads string literals out of
    that function's body. This is the half of that contract JG2 owns.
    """
    path = _client(_CLIENT_CHANNELS)
    assert path is not None
    source = path.read_text(encoding="utf-8")
    assert f"'{CHECK_IN_CHANNEL}'" in source, (
        f"the backend sends channelId {CHECK_IN_CHANNEL!r}, which {path.name} does "
        "not create. Android will file it under a fallback channel with default "
        "importance and no sound -- silently."
    )


@needs_client
def test_the_action_ids_match_the_client():
    path = _client(_CLIENT_CHECK_IN)
    assert path is not None
    source = path.read_text(encoding="utf-8")

    category = re.search(r"CHECK_IN_ACTION_CATEGORY = '([^']+)'", source)
    assert category, f"CHECK_IN_ACTION_CATEGORY not found in {path.name}"
    assert category.group(1) == CHECK_IN_ACTION_CATEGORY, (
        "the app registers its action buttons under a different category id than "
        "the backend names on the message. The notification arrives with NO "
        "BUTTONS, and nothing reports it."
    )

    action = re.search(r"CHECK_IN_ACTION_OK = '([^']+)'", source)
    assert action, f"CHECK_IN_ACTION_OK not found in {path.name}"
    assert action.group(1) == CHECK_IN_ACTION_OK


@needs_client
def test_the_grace_period_the_planner_promises_is_the_one_the_server_uses():
    """
    The planner says "Check in by 10:40" before the journey exists, which it can
    only do by knowing the server's grace period. If the two drift, the person is
    told 10:40 and asked at 10:55.
    """
    path = _client(_CLIENT_DEADLINE)
    assert path is not None
    match = re.search(
        r"SERVER_GRACE_MINUTES = (\d+)", path.read_text(encoding="utf-8")
    )
    assert match, f"SERVER_GRACE_MINUTES not found in {path.name}"
    assert timedelta(minutes=int(match.group(1))) == GRACE


def test_the_migration_backfill_uses_the_same_grace_period():
    """
    Journeys that existed before this phase get the deadline they would have been
    given. A backfill that disagreed with the code would make old journeys behave
    unlike new ones with nothing to say why.
    """
    match = re.search(r"set deadline_at = eta_at \+ interval '(\d+) minutes'", _sql())
    assert match, "the backfill in the migration is not in the shape this test reads"
    assert timedelta(minutes=int(match.group(1))) == GRACE


# ---------------------------------------------------------------------------
# JG2 stops here
# ---------------------------------------------------------------------------


def test_the_check_in_itself_still_involves_no_guardian():
    """
    This was `test_no_guardian_or_contact_anywhere_in_this_phase`, and it
    covered the sweep too -- deliberately, as JG2's scope line. JG3 crossed that
    line on purpose: `journey_watch` now joins `emergency_contacts` to send the
    started and arrived notices, so the sweep is no longer in scope for this
    rule and asserting otherwise would just block the phase it was written to
    announce.

    What is still true, and still worth a test, is the narrower claim:

    * **JG2's migration is frozen.** It is forward-only and applied; a guardian
      column appearing in it now would mean somebody edited a file that other
      databases have already run, which is the one thing `migrate.py`'s
      checksum exists to catch.
    * **The check-in message has no guardian in it.** The push goes to the
      traveller's own phone and asks them a question. That is as true in JG3 as
      it was in JG2 -- the guardian is told by email, from the sweep, in a
      different message composed in a different module. If a guardian ever
      appears in `checkin.py`, the thing that arrives on a lock screen has
      started naming a second person, and `JOURNEY_GUARDIAN.md` §5 is explicit
      that a lock screen is visible to whoever is standing next to you.
    """
    for path in (MIGRATION, BACKEND / "app" / "journeys" / "checkin.py"):
        source = path.read_text(encoding="utf-8").lower()
        statements = re.sub(r"--[^\n]*", "", source)
        statements = re.sub(r'"""', "", statements)
        # Identifiers, not the word. `guardian` on its own matches the prose
        # reference to `JOURNEY_GUARDIAN.md §5` in `checkin.py` -- which is the
        # reason the original version of this test said `guardian_id` and not
        # `guardian`, and the reason broadening it was a mistake.
        for forbidden in ("guardian_contact", "guardian_id", "emergency_contact", "contacts_notified"):
            assert forbidden not in statements, f"{forbidden!r} in {path.name} is JG3"


def test_this_migration_still_stores_no_position():
    """
    This was `test_the_heartbeat_carries_no_position`, and it asserted
    `JourneyHeartbeat.model_fields == {"remaining_seconds"}`. Its own docstring
    named the condition under which it should go:

        The only message that needs a last known position is the escalation JG3
        sends to somebody else, and a location written before there is anything
        to do with it is the privacy surface JG1 refused for the same reason.

    JG3 is now that reader, so the heartbeat carries an optional position and
    this file's claim over the schema has ended. The replacement invariant lives
    in `test_journey_guardian.py`, and it is narrower but still real: a position
    is stored **only for a journey that has a guardian**, which is the privacy
    rule applied at the point of collection rather than at the point of use.

    What is still checked here is that **JG2's migration** never grew one. It is
    forward-only and already applied to databases other than this one; a
    position column appearing in it now would mean the file was edited after the
    fact, which is what `migrate.py`'s checksum exists to catch.
    """
    statements = re.sub(r"--[^\n]*", "", _sql())
    for forbidden in ("latitude", "longitude", "last_position", "st_makepoint"):
        assert forbidden not in statements.lower(), (
            f"{forbidden!r} in the JG2 migration: this phase stored no position"
        )


def test_the_check_in_window_is_not_also_the_grace_period():
    """
    Two different questions -- how long before we ask, and how long we wait for
    an answer -- and collapsing them into one number is the commonest way a
    timing module stops being adjustable. JG4 moves `GRACE` with the risk score;
    `CHECK_IN_WINDOW` is about how long a phone takes to come back from a
    coverage gap, which has nothing to do with the route.
    """
    assert CHECK_IN_WINDOW != GRACE
    assert ANSWER_EXTENSION != GRACE


# ---------------------------------------------------------------------------
# The leash: a chosen deadline survives the heartbeat
# ---------------------------------------------------------------------------
# Every test below exists because of one bug, found the first time this phase ran
# on a phone. Somebody started a three-minute walk, chose `2 min`, and sixty
# seconds later their own heartbeat had moved the deadline to twelve minutes out.
# The check-in they were waiting for never came.


def test_accepting_the_route_eta_sets_no_leash():
    """
    `None` means "derive it from what is left of the route", not "no limit".

    The difference matters: a None that meant unlimited would make the default
    chip the one with no ceiling, which is the opposite of the intent.
    """
    assert leash(chosen_minutes=None) is None


def test_a_chosen_deadline_is_also_a_leash():
    assert leash(chosen_minutes=2) == timedelta(minutes=2)
    assert leash(chosen_minutes=60) == timedelta(hours=1)


def test_the_leash_is_clamped_like_the_deadline_it_came_from():
    """
    The two have to agree, or the first heartbeat moves the deadline somewhere
    the initial one was not allowed to be.
    """
    assert leash(chosen_minutes=1) == MIN_DEADLINE
    assert leash(chosen_minutes=10_000) == MAX_DEADLINE
    for chosen in (1, 2, 30, 60, 10_000):
        assert leash(chosen_minutes=chosen) == start_offset(
            duration_minutes=999, chosen_minutes=chosen
        )


def test_the_heartbeat_is_capped_by_the_leash():
    """
    THE regression test for this phase.

    Without `least(:slide_seconds, coalesce(leash_seconds, :slide_seconds))` a
    two-minute leash becomes twelve the moment the phone reports in -- the
    proposal carries a full grace period on top of the route's remainder, and
    `greatest` takes it because it is later.
    """
    sql = _endpoint()
    heartbeat = sql[sql.index("_HEARTBEAT") : sql.index("_CHECK_IN")]
    assert "coalesce(leash_seconds, :slide_seconds)" in heartbeat, (
        "the heartbeat no longer caps its proposal by the chosen leash. A person "
        "who asked to be checked on in two minutes will be given ten by their "
        "own phone, silently."
    )
    # The cap is applied to the *proposal*, inside `greatest`, not outside it --
    # outside, `greatest(deadline_at, ...)` would already have taken the
    # uncapped value and the cap would be reading a number nothing used.
    inner = heartbeat[heartbeat.index("greatest(") : heartbeat.index("-- The ceiling")]
    assert "coalesce(leash_seconds, :slide_seconds)" in inner


def test_no_leash_leaves_the_heartbeat_exactly_as_it_was():
    """
    `coalesce(leash_seconds, :slide_seconds)` rather than a second branch: with
    no leash the cap is the proposal, so `least` is the identity and the default
    path is unchanged. A `case` here would have been two code paths where one
    will do.
    """
    sql = _endpoint()
    heartbeat = sql[sql.index("_HEARTBEAT") : sql.index("_CHECK_IN")]
    assert "coalesce(leash_seconds, :slide_seconds)" in heartbeat


def test_the_answer_is_capped_by_the_leash():
    """
    The second half of the same bug, found on the same device row one path over.

    Two things move a deadline, and `20261015140000__journey_leash.sql` capped
    one of them. The row read: `leash_seconds = 120`, answered at 10:59:22,
    `deadline_at = 11:14:22` -- fifteen minutes handed to somebody who had asked
    to be checked on every two, for tapping the button they were asked to tap.

    `ANSWER_EXTENSION` is a guess. A leash is something the person said. The
    guess does not get to overrule the statement, which is the whole argument of
    the migration, and it does not stop being true because this is the answer
    path rather than the heartbeat path.
    """
    sql = _endpoint()
    answer = sql[sql.index("_CHECK_IN") : sql.index("def _response")]
    assert "coalesce(leash_seconds, :extension_seconds)" in answer, (
        "answering no longer caps its extension by the chosen leash. A person "
        "who asked to be checked on in two minutes gets fifteen for answering, "
        "which is the heartbeat bug in the other path."
    )


def test_no_leash_leaves_the_answer_at_the_full_extension():
    """
    `coalesce` again, for the reason it is used in the heartbeat: with no leash
    the cap is the extension, `least` is the identity, and the default chip --
    the common case -- behaves exactly as it did. Only a leash *shorter* than
    fifteen minutes changes anything, which among the chips is just `2 min`.
    """
    assert ANSWER_EXTENSION == timedelta(minutes=15)
    for choice in (30, 60):
        chip = leash(chosen_minutes=choice)
        assert chip is not None
        assert chip > ANSWER_EXTENSION, (
            "a chip between MIN_DEADLINE and ANSWER_EXTENSION would be silently "
            "shortened by the answer path; this test is the warning that the "
            "walkthrough's step 10 would need rewriting"
        )


def test_the_leash_is_written_at_start_and_never_again():
    """
    It is the record of a choice, so nothing may revise it. A heartbeat that
    could write it would be the phone editing the instruction it was given.
    """
    sql = _endpoint()
    # Four mentions, all reads or an insert: the INSERT's column list, the
    # `:leash_seconds` bound to it, and the two `coalesce` caps -- one in the
    # heartbeat, one in the answer. A fifth would most likely be an UPDATE,
    # which is the thing this test forbids.
    assert len(re.findall(r"leash_seconds", _endpoint_sql())) == 4, (
        "expected leash_seconds exactly four times in the endpoint's SQL: the "
        "INSERT's column list, its bound parameter, and the two caps -- the "
        "heartbeat's and the answer's"
    )
    assert ":leash_seconds" in sql
    assert not re.search(r"leash_seconds\s*=", sql), "something assigns to leash_seconds"


def test_the_sweep_never_touches_the_leash():
    assert "leash" not in AGENT.read_text(encoding="utf-8")


def test_the_database_backstops_the_clamp():
    """
    `journeys_leash_sane`. The clamp lives in Python; this is what makes it a
    guarantee rather than a convention, in the same spirit as every other CHECK
    on this table.
    """
    sql = LEASH_MIGRATION.read_text(encoding="utf-8")
    assert "journeys_leash_sane" in sql
    match = re.search(
        r"leash_seconds >= (\d+) and leash_seconds <= (\d+)", sql
    )
    assert match, "the leash bounds are not in the shape this test reads"
    assert timedelta(seconds=int(match.group(1))) == MIN_DEADLINE
    assert timedelta(seconds=int(match.group(2))) == MAX_DEADLINE


def test_the_leash_migration_requires_the_one_before_it():
    sql = LEASH_MIGRATION.read_text(encoding="utf-8")
    guard = sql[: sql.index("alter table public.journeys")]
    assert "raise exception" in guard
    assert "journeys_escalation_check" in guard
