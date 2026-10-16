"""
JG3 — someone else knows. The invariants that must not quietly change.

Same approach as `test_journey_deadline.py`: the migration and the endpoint SQL
are read as text, because what matters here is not that a function returns the
right number but that a *rule* exists in the place that cannot be bypassed.

The rule this file exists for is one sentence from JOURNEY_GUARDIAN.md §7:

    Every step past the first requires a recorded non-response with a timestamp.
    It cannot jump to panic.

Everything below is that sentence, checked from a different angle each time. The
reason it is worth this much test code is the failure mode: the bug is not a
crash, it is an email to somebody's mother at midnight because her daughter
stopped for tea, and one of those ends the feature.
"""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# `_ALERT` is private on purpose -- the palette is an implementation detail of
# the layout. It is imported anyway because "the calm notices are not red" is a
# product rule, and a test that hard-coded the hex would stop checking it the
# day somebody picked a different red.
from app.journeys.guardian import (
    _ALERT,
    GuardianMessage,
    Position,
    arrived_message,
    escalation_message,
    started_message,
)
from app.models.journey import (
    ESCALATION_CHECK_IN_REPEATED,
    ESCALATION_CHECK_IN_SENT,
    ESCALATION_CONTACTS_NOTIFIED,
    ESCALATION_FULL_SOS,
    ESCALATION_LADDER,
    ESCALATION_NORMAL,
    ESCALATION_RECORDED_AT,
    ESCALATION_STATES,
    ESCALATION_TRANSITIONS,
    may_escalate,
    next_escalation,
)
from app.schemas.journey import JourneyHeartbeat, JourneyStart

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "migrations" / "versions" / "20261015180000__journey_guardian.sql"
#: The correction to the migration above, one bug wide. See
#: `test_the_notice_check_is_gone_and_stays_gone`.
FOLLOWUP = (
    BACKEND
    / "migrations"
    / "versions"
    / "20261015190000__guardian_notice_outlives_the_contact.sql"
)


def _migration() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _followup() -> str:
    return FOLLOWUP.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The machine
# ---------------------------------------------------------------------------


def test_the_five_states_are_the_five_rings():
    assert ESCALATION_STATES == (
        "normal",
        "check_in_sent",
        "check_in_repeated",
        "contacts_notified",
        "full_sos",
    )


def test_the_ladder_excludes_normal():
    """
    `normal` is not a ring. It is the absence of one, and a ladder containing it
    would make "escalate one step" able to return to calm.
    """
    assert ESCALATION_NORMAL not in ESCALATION_LADDER
    assert len(ESCALATION_LADDER) == len(ESCALATION_STATES) - 1


def test_every_state_names_the_python_and_the_sql_the_same():
    """
    The CHECK is the only thing stopping a typo from becoming a state no code
    can leave. A name misspelled on one side is an IntegrityError on a real
    journey at the worst possible moment.
    """
    sql = _migration()
    listed = re.search(
        r"escalation_state in \(([^)]*)\)", sql, re.S
    )
    assert listed, "the escalation CHECK is not in the shape this test reads"
    names = set(re.findall(r"'([a-z_]+)'", listed.group(1)))
    assert names == set(ESCALATION_STATES)


def test_escalation_moves_exactly_one_ring():
    """
    The whole of "it cannot jump to panic", as a property of the table.

    Checked exhaustively rather than by example: for every pair of states, the
    edge exists only if it is one step forward or a return to `normal`.
    """
    for current in ESCALATION_STATES:
        for target in ESCALATION_STATES:
            allowed = may_escalate(current, target)
            if target == ESCALATION_NORMAL:
                # From anywhere except itself: answering ends it.
                assert allowed is (current != ESCALATION_NORMAL), (current, target)
                continue
            expected = next_escalation(current) == target
            assert allowed is expected, (
                f"{current} -> {target} is {'allowed' if allowed else 'refused'} "
                "and should not be; escalation moves one ring at a time"
            )


def test_no_state_can_skip_to_full_sos():
    """
    The specific jump that matters, named so a failure says what broke.

    `full_sos` emails every contact. Reaching it from anything but
    `contacts_notified` means somebody's whole contact list was mailed without
    the ring before it having happened.
    """
    for current in ESCALATION_STATES:
        if current == ESCALATION_CONTACTS_NOTIFIED:
            continue
        assert not may_escalate(current, ESCALATION_FULL_SOS), current


def test_full_sos_is_terminal_apart_from_an_answer():
    """
    There is no sixth ring. JG7's witnesses are fired by a *confirmed*
    emergency -- full SOS or the duress response -- and never by an unanswered
    check-in, because an unanswered check-in is usually a phone in a bag. An
    edge out of here would be the thing JOURNEY_GUARDIAN.md §8 refuses.
    """
    assert ESCALATION_TRANSITIONS[ESCALATION_FULL_SOS] == (ESCALATION_NORMAL,)
    assert next_escalation(ESCALATION_FULL_SOS) is None


def test_an_answer_ends_it_from_every_ring():
    """
    Not only from `check_in_sent`. A journey that reached `contacts_notified`
    and is then answered has to go quiet, or answering would be useless exactly
    when it matters most.
    """
    for state in ESCALATION_LADDER:
        assert may_escalate(state, ESCALATION_NORMAL), state


def test_every_ring_records_when_it_happened():
    """
    A ring with no timestamp cannot gate the ring after it, which is how a step
    gets skipped.
    """
    assert set(ESCALATION_RECORDED_AT) == set(ESCALATION_LADDER)
    sql = _migration()
    for state, column in ESCALATION_RECORDED_AT.items():
        if state == ESCALATION_CHECK_IN_SENT:
            continue  # JG2's column, added by its own migration.
        assert column in sql, f"{state} records into {column}, which this migration never adds"


# ---------------------------------------------------------------------------
# The same rules, in the database
# ---------------------------------------------------------------------------


def test_each_state_requires_its_own_timestamp():
    sql = _migration()
    for name in (
        "journeys_repeated_before_waiting",
        "journeys_contacts_before_waiting",
        "journeys_sos_before_waiting",
    ):
        assert name in sql, f"{name} is missing: a state could be set with no record of it"


def test_the_ordering_rules_are_in_the_table_not_only_the_sweep():
    """
    The three CHECKs that make the escalation invariant a property of the
    database. The sweep writes these transitions and the sweep could have a bug;
    a CHECK turns that bug into an IntegrityError instead of an email.
    """
    sql = _migration()
    for name in (
        "journeys_repeated_after_asked",
        "journeys_contacts_after_repeated",
        "journeys_sos_after_contacts",
    ):
        assert name in sql, f"{name} is missing: the escalation chain could skip a step"


def test_the_ordering_rules_are_one_directional():
    """
    A journey that escalated and was then answered returns to `normal` and keeps
    its timestamps -- they are the history of what happened on this trip, and
    JG3's journey screen renders them. A biconditional would force the sweep to
    erase that history to calm a journey down.
    """
    sql = _migration()

    def body_of(name: str) -> str | None:
        """
        The CHECK body for one constraint, and nothing else.

        Sliced to the statement's own `end if;` rather than matched with a
        non-greedy regex: the bodies contain their own brackets, and a `(.*?)`
        looking for a closing paren walked straight past
        `journeys_escalation_check`'s `));` into the next constraint's -- which
        made this test silently read the wrong rule.
        """
        marker = f"add constraint {name}"
        if marker not in sql:
            return None
        start = sql.index(marker)
        return sql[start : sql.index("end if;", start)]

    for name, later, earlier in (
        ("journeys_repeated_after_asked", "check_in_repeated_at", "check_in_sent_at"),
        ("journeys_contacts_after_repeated", "contacts_notified_at", "check_in_repeated_at"),
        ("journeys_sos_after_contacts", "full_sos_at", "contacts_notified_at"),
    ):
        body = body_of(name)
        assert body, f"{name} is missing from the migration"
        # "this one is null OR the one before it happened and came first" --
        # never a biconditional, which would force the sweep to erase history
        # to calm a journey down.
        assert f"{later} is null" in body, (
            f"{name} must permit a null, or an un-escalated journey cannot exist"
        )
        assert f"{earlier} is not null" in body, (
            f"{name} does not require {earlier}, so its step could be skipped"
        )
        assert f">= {earlier}" in body, (
            f"{name} does not require its own timestamp to come after {earlier}"
        )


def test_a_guardian_is_a_reference_and_survives_a_deleted_contact():
    """
    `on delete set null`, not cascade and not restrict.

    Cascade would delete somebody's journey history because they tidied their
    contacts. Restrict would make a contact undeletable while any old journey
    pointed at them, which turns "remove this person from my life" into an
    error message.
    """
    sql = _migration()
    assert "journeys_guardian_contact_fk" in sql
    assert "references public.emergency_contacts(id) on delete set null" in sql


def test_a_journey_with_no_guardian_is_valid():
    """
    The private case. `guardian_contact_id` is nullable and no CHECK requires
    it, because a journey nobody is told about is JG2's behaviour and has to
    keep working for somebody with no contacts saved.
    """
    sql = _migration()
    assert "add column if not exists guardian_contact_id uuid;" in sql
    assert not re.search(r"guardian_contact_id\s+uuid\s+not null", sql)


def test_nobody_is_told_about_a_journey_with_no_guardian():
    """
    The inverse of the test above. It is enforced where the telling happens --
    every notice query joins `emergency_contacts` through
    `guardian_contact_id`, so a journey with no guardian is never selected by
    any of them -- and **not** by a CHECK on the row.

    It was a CHECK for exactly one migration. `journeys_notice_needs_guardian`
    read "a notice timestamp requires a guardian", which is true of the moment a
    notice is sent and false of a row: `on delete set null` leaves a journey
    whose guardian was emailed and has since been deleted, and the CHECK
    rejected it -- turning a `DELETE` on the contact into an IntegrityError and
    making any contact ever used as a guardian undeletable. See
    `20261015190000__guardian_notice_outlives_the_contact.sql`.
    """
    agent = _agent_sql()
    # Three senders, three joins. The join is the rule.
    assert agent.count("join public.emergency_contacts c on c.id = j.guardian_contact_id") >= 3


def _constraint_state() -> dict[str, str]:
    """
    Every CHECK this project has ever added that requires a live guardian, and
    whether the migrations end up with it or without it.

    Applied in filename order, which is the order `migrate.py` applies them, so
    "added in one file and dropped in a later one" comes out as `dropped` --
    the state of the schema rather than the content of any one file. The
    alternative, grepping a single migration, is what let the bug below ship:
    both files were individually right.
    """
    state: dict[str, str] = {}
    for path in sorted((BACKEND / "migrations" / "versions").glob("*.sql")):
        body = path.read_text(encoding="utf-8")
        # Comments quote the bug they describe -- this file's own header quotes
        # the dropped CHECK in full -- so the prose is stripped first.
        code = chr(10).join(
            line for line in body.splitlines() if not line.strip().startswith("--")
        )
        for name, body_of in re.findall(
            r"add constraint (\w+)\s+check \(([^;]*)", code, re.S
        ):
            if "guardian_contact_id is not null" in body_of:
                state[name] = "present"
        for name in re.findall(r"drop constraint (?:if exists )?(\w+)", code):
            if name in state:
                state[name] = "dropped"
    return state


def test_no_constraint_requires_a_live_guardian():
    """
    The bug, stated as the rule it broke.

    Two things in `20261015180000` contradicted each other and both passed
    their own tests: the foreign key's `on delete set null`, whose comment says
    it exists to avoid *"a blocked delete"*, and `journeys_notice_needs_guardian`
    two sections later, which required a notice timestamp to have a guardian
    beside it. Deleting a contact set that column to null on their old
    journeys, the CHECK rejected the resulting row, and the `DELETE` failed --
    so any contact ever used as a guardian became undeletable and the contacts
    screen could only say "Failed to delete contact".

    Neither test ran a delete. Found by running one against the real table in a
    rolled-back transaction, and corrected by
    `20261015190000__guardian_notice_outlives_the_contact.sql`.

    Phrased over the final schema rather than over one file, because the
    reintroduction worth catching is a future phase re-deriving the same rule
    and adding it back under a different name.
    """
    live = {name for name, state in _constraint_state().items() if state == "present"}
    assert live == set(), (
        "these CHECKs require a live guardian, which turns deleting that "
        f"contact into an IntegrityError: {sorted(live)}"
    )


def test_the_notice_check_was_added_and_then_dropped():
    """
    Specifically that one, by name, so the history stays legible: the file that
    added it is applied and checksummed and cannot be edited, so the record of
    it being wrong lives in the migration that drops it.
    """
    assert _constraint_state().get("journeys_notice_needs_guardian") == "dropped"
    assert "drop constraint if exists journeys_notice_needs_guardian" in _followup()


# ---------------------------------------------------------------------------
# The position
# ---------------------------------------------------------------------------


def test_a_position_arrives_with_its_timestamp_or_not_at_all():
    """
    "Last seen here" with no "when" is the half-truth that sends somebody to the
    wrong place. A time with no point reads as though a position is known.
    """
    sql = _migration()
    assert "journeys_position_paired" in sql
    assert "(last_position is null) = (last_position_at is null)" in sql


def test_the_position_is_one_point_and_not_a_log():
    """
    JOURNEY_GUARDIAN.md JG1 settled this: one row, because a log is only needed
    once JG5 wants history, and JG5 is not being built. A log shipped now would
    be a privacy surface with no reader -- which is the exact argument JG2 used
    to refuse storing a position at all.
    """
    sql = _migration()
    assert "create table" not in sql.lower(), "JG3 adds no table; the position is one column"
    assert "last_position" in sql


def test_the_position_is_a_geography_in_the_extensions_schema():
    """
    The project's PostGIS idiom. A bare `geography` resolves only if the search
    path happens to include `extensions`, and it does not in a migration.
    """
    sql = _migration()
    assert "last_position        extensions.geography" in sql


# ---------------------------------------------------------------------------
# Guards, because create_all races hand-written migrations
# ---------------------------------------------------------------------------


def test_the_migration_refuses_to_run_out_of_order():
    """
    `Base.metadata.create_all` runs at every app start and builds any table a
    model declares, so `create table if not exists` silently skips and a
    migration's constraints never land. JG1 lost a day to it and both JG2
    migrations carry this guard.

    This one checks three things rather than one, because JG3 depends on JG2's
    deadline columns, JG2's leash fix, and a table from an entirely different
    sprint.
    """
    sql = _migration()
    assert sql.count("raise exception") >= 3
    assert "journeys_escalation_check" in sql
    assert "leash_seconds" in sql
    assert "emergency_contacts" in sql


def test_the_sweep_gets_an_index_for_its_new_scans():
    """
    `journey_watch` goes from two scans a minute to five. JG2's
    `idx_journeys_due` covers the deadline scan only.
    """
    sql = _migration()
    assert "idx_journeys_escalating" in sql
    assert "where state = 'active'" in sql


# ---------------------------------------------------------------------------
# What the second person is told, and what they are not
# ---------------------------------------------------------------------------
# JOURNEY_GUARDIAN.md §2: "He only learns *where* she is if something actually
# goes wrong. She gets watched over without being surveilled."
#
# Tested in BOTH directions. A privacy rule checked only one way -- "this
# message contains no coordinates" -- passes trivially on a function that
# returns the empty string, or on one somebody later stops calling. The inverse
# test is what proves the first one is measuring something.

GUARDIAN = BACKEND / "app" / "journeys" / "guardian.py"

_DUE = datetime(2026, 10, 15, 16, 40, tzinfo=UTC)
_HERE = Position(latitude=23.75092, longitude=90.39342, at=_DUE)
#: Where a journey began, for the fallback. A different point from `_HERE` on
#: purpose: a test that uses one coordinate for both cannot tell which the
#: message rendered.
_START = Position(latitude=23.81031, longitude=90.41250, at=_DUE)

#: Anything that looks like a decimal coordinate pair.
_COORD_RE = re.compile(r"-?\d{1,3}\.\d{3,}")


def test_the_started_notice_cannot_be_given_a_position():
    """
    Not "does not" -- *cannot*. The signature has no parameter for one, so a
    later edit that helpfully adds the location to this email has to change the
    function's interface and trip this test, rather than quietly widening what
    the guardian learns.
    """
    params = set(inspect.signature(started_message).parameters)
    assert params == {"traveller", "destination", "due_by"}
    assert not {"last_seen", "position", "latitude", "longitude"} & params


def test_the_arrived_notice_cannot_be_given_a_position():
    params = set(inspect.signature(arrived_message).parameters)
    assert params == {"traveller", "at"}
    assert not {"last_seen", "position", "latitude", "longitude"} & params


def test_neither_calm_notice_renders_a_coordinate():
    """
    The signature test above and this one catch different bugs: that one catches
    a widened interface, this one catches a coordinate arriving through an
    argument that is not obviously one -- a destination string built from a
    reverse geocode, say.

    **All three parts**, which is the point of reading `html` here. The HTML
    half was added for looks, and a layout is exactly where somebody later adds
    a helpful map thumbnail to the "she set off" notice without noticing they
    have moved the privacy line. If it can be rendered, it is covered.
    """
    for message in (
        started_message(traveller="Rina", destination="Mirpur", due_by=_DUE),
        arrived_message(traveller="Rina", at=_DUE),
    ):
        rendered = f"{message.subject}\n{message.body}\n{message.html}"
        assert not _COORD_RE.search(rendered), rendered
        assert "maps" not in rendered.lower()
        assert "http" not in rendered.lower()


def test_the_escalation_does_render_the_coordinate():
    """
    The inverse, and the reason the three tests above are not vacuous.

    If this fails while they pass, the privacy rule has become "say nothing to
    anybody", which is not a feature.
    """
    message = escalation_message(
        traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
    )
    assert _COORD_RE.search(message.body)
    assert "maps" in message.body.lower()
    assert message.urgent is True


def test_the_escalation_says_so_when_there_is_nothing_at_all():
    """
    Neither a fix nor a start point. Silently omitting the location would read
    as though none was ever taken -- where "we do not know where she is" is the
    most important fact in that email.

    Reachable only through this function's own interface now: `origin` is `not
    null` on every journey, so the sweep always has a start point to pass. The
    branch stays because this module is pure and must answer for its arguments
    rather than for one caller's schema.
    """
    message = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=None,
        started_from=None,
    )
    assert not _COORD_RE.search(message.body)
    assert "not reported a location" in message.body


def test_the_escalation_falls_back_to_where_they_set_off():
    """
    The case the first device run produced, which nothing had allowed for: a
    journey heartbeated for twenty minutes and stored no position, because the
    navigator drops fixes worse than 100 m accuracy and indoors that is all of
    them. The most important message this product sends had no point in it.

    `origin` costs nothing to use -- it is `not null` on every journey because
    the route was planned from it -- so the escalation now always has somewhere
    to point.
    """
    message = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=None,
        started_from=_START,
    )
    assert _COORD_RE.search(message.body), message.body
    assert "maps" in message.body.lower()
    assert message.urgent is True


def test_the_start_point_is_never_dressed_up_as_a_sighting():
    """
    The reason the fallback is a separate sentence rather than the same one with
    an older timestamp.

    Somebody reading this skims for "where was she last" and acts on the
    answer. A start point presented under that heading sends a searcher to the
    wrong end of a route -- which is worse than being told there is no sighting,
    because it is confidently wrong.
    """
    fallback = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=None,
        started_from=_START,
    ).body
    assert "last place their phone reported from" not in fallback
    assert "started from" in fallback
    assert "not a sighting" in fallback


def test_a_real_fix_always_beats_the_start_point():
    """
    The fallback is a fallback. Given both, the message describes the fix -- and
    says nothing about where the journey began, because two points in one email
    is how a reader ends up at the wrong one.
    """
    body = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=_HERE,
        started_from=_START,
    ).body
    assert "last place their phone reported from" in body
    assert f"{_START.latitude:.5f}" not in body
    assert "started from" not in body


def test_the_start_point_cannot_reach_a_calm_notice():
    """
    The fallback widened one signature, so the privacy rule is re-checked on
    the other two: neither calm notice can accept a start point either, by any
    name.
    """
    for composer in (started_message, arrived_message):
        params = set(inspect.signature(composer).parameters)
        assert not {"started_from", "origin", "last_seen", "position"} & params


# ---------------------------------------------------------------------------
# Names and places, as they actually arrive
# ---------------------------------------------------------------------------
# All three found by rendering a real journey rather than a fixture, which is
# the only reason they were found at all: every test above used "Rina" and
# "Mirpur".

#: The destination label on the first real guardian journey, verbatim. A POI
#: tapped from the map carries whatever the place is called, which here is four
#: lines in two scripts.
_REAL_LABEL = (
    "National Museum of\nScience and Technology\n"
    "\u099c\u09be\u09a4\u09c0\u09af\u09bc \u09ac\u09bf\u099c\u09cd\u099e\u09be\u09a8 \u0993\n"
    "\u09aa\u09cd\u09b0\u09af\u09c1\u0995\u09cd\u09a4\u09bf \u099c\u09be\u09a6\u09c1\u0998\u09b0"
)


def test_a_multi_line_place_name_renders_as_one_line():
    """
    The label above turned the most important sentence in the escalation email
    into four broken ones -- at the moment a guardian most needs to believe the
    software is working. Nothing in the suite could see it, because every
    fixture used a tidy name.
    """
    for message in (
        started_message(traveller="Rina", destination=_REAL_LABEL, due_by=_DUE),
        escalation_message(
            traveller="Rina",
            destination=_REAL_LABEL,
            started_at=_DUE,
            last_seen=_HERE,
        ),
    ):
        # The label arrives as four lines; it has to leave as part of one. A
        # test on "no newlines in the body" would be wrong -- the escalation
        # body is several paragraphs by design -- so this asserts the thing
        # that actually broke: the place name is contiguous, on one line.
        assert "National Museum of Science and Technology" in message.body
        assert _REAL_LABEL not in message.body
        assert chr(10) not in message.subject
        # And no line of the rendered message is a stray fragment of the label.
        assert "Science and Technology" not in message.body.split(chr(10))


def test_a_name_with_a_newline_cannot_reach_a_subject_line():
    """
    Not an injection -- Python raises `HeaderParseError` rather than flattening
    an embedded header -- which is worse than it sounds. The transport catches,
    reports a failed send, and the notice has **already been marked sent**. One
    newline in a display name would mean that person's guardian is silently
    never told anything again, on every journey.
    """
    nasty = "Rina" + chr(10) + "Bcc: somebody@example.com"
    for message in (
        started_message(traveller=nasty, destination="Mirpur", due_by=_DUE),
        arrived_message(traveller=nasty, at=_DUE),
        escalation_message(
            traveller=nasty, destination="Mirpur", started_at=_DUE, last_seen=None
        ),
    ):
        assert chr(10) not in message.subject
        assert "\r" not in message.subject
        assert "Bcc:" not in message.subject.replace("Bcc: somebody", "")


def test_the_transport_folds_its_own_subject():
    """
    The second half of the same rule, at the point where a header is actually
    written. `guardian.py` owns the wording and collapses what it renders; this
    is here because `send_guardian_message` takes a subject from any caller.
    """
    source = _code_only(
        (BACKEND / "app" / "services" / "email_service.py").read_text(encoding="utf-8")
    )
    body = source[source.index("async def send_guardian_message") :]
    body = body[: body.index("async def") + 1] if "async def" in body[20:] else body
    assert 'msg["Subject"] = " ".join(subject.split())' in body


def test_a_very_long_place_name_is_capped_rather_than_sent_whole():
    """
    `destination_label` is bounded at 200 characters by the wire schema, which
    is a reasonable column width and far too long for "they were heading for X".
    Capped with an ellipsis so a truncated name still reads as a name.
    """
    long_name = "Shahjalal " * 30
    body = escalation_message(
        traveller="Rina", destination=long_name, started_at=_DUE, last_seen=_HERE
    ).body
    assert "Shahjalal" in body
    assert len(max(body.split(chr(10)), key=len)) < 200
    assert "\u2026" in body


def test_a_position_cannot_exist_without_its_timestamp():
    """
    `Position.at` is required, mirroring `journeys_position_paired` in the
    table. A coordinate with no time is what sends somebody to where she was
    forty minutes ago believing it is where she is now.
    """
    params = inspect.signature(Position).parameters
    assert params["at"].default is inspect.Parameter.empty


def test_the_escalation_never_describes_a_position_as_current():
    """
    The sentence that keeps the email honest. `last_position` is the last point
    the phone *reported*, which on a dead phone may be half an hour old.
    """
    message = escalation_message(
        traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
    )
    assert "not necessarily where" in message.body


def test_the_calm_notices_do_not_read_like_an_emergency():
    """
    Two messages a night that look urgent get filtered, and then the one that
    matters lands in a folder nobody opens. `email_service.py`'s only existing
    template is subject-lined "EMERGENCY: {name} needs help"; these are not that.
    """
    for message in (
        started_message(traveller="Rina", destination="Mirpur", due_by=_DUE),
        arrived_message(traveller="Rina", at=_DUE),
    ):
        assert message.urgent is False
        assert "emergency" not in message.subject.lower()
        assert "help" not in message.subject.lower()
        # And it is not red. The palette is the tone before a word is read: a
        # guardian who gets a red-banded email about somebody leaving the house
        # learns that red bands are nothing.
        assert _ALERT.band not in message.html
        assert _ALERT.accent not in message.html


def test_the_escalation_tells_its_reader_they_are_the_only_one():
    """
    The reader has to know nobody else is handling this, or they will wait for
    somebody who does not exist.

    It is also simply true now. There was a further rung that mailed the
    traveller's whole contact list, and the message had a second sentence for
    it; the rung was removed, so the claim is unconditional and this is what
    keeps it honest if a fan-out is ever added back without the wording.
    """
    message = escalation_message(
        traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
    )
    assert "You are the only person who has been told." in message.body
    assert "You are the only person who has been told." in message.html
    for claim in ("contact list", "somebody else may already", "everyone"):
        assert claim not in message.body.lower()


def test_no_message_tells_anybody_to_call_the_police():
    """
    999 and the thana record are JG7. JOURNEY_GUARDIAN.md is explicit that
    reaching full escalation from an unanswered check-in and then contacting
    police would be the most damaging false positive this product can produce --
    and an email that *instructs* a guardian to do it is the same act with an
    extra step.
    """
    bodies = [
        part
        for message in (
            started_message(traveller="R", destination="M", due_by=_DUE),
            arrived_message(traveller="R", at=_DUE),
            escalation_message(
                traveller="R", destination="M", started_at=_DUE, last_seen=_HERE
            ),
            escalation_message(
                traveller="R",
                destination="M",
                started_at=_DUE,
                last_seen=None,
            ),
        )
        # Both halves. The SOS template has a "call 999" step in its HTML and
        # these are laid out to look like it, which is precisely the pull this
        # has to resist.
        for part in (message.body, message.html)
    ]
    for body in bodies:
        low = body.lower()
        for word in ("999", "police", "thana", "ambulance"):
            assert word not in low, f"{word!r} appears in a JG3 message: {body}"


def test_times_are_shown_in_dhaka_not_utc():
    """
    The server's clock is UTC and the guardian is a person in Bangladesh. Six
    hours is the difference between "she is an hour late" and "she is fine",
    read by somebody deciding whether to get in a car.
    """
    # 16:40 UTC is 22:40 in Dhaka.
    message = arrived_message(traveller="Rina", at=_DUE)
    assert "10:40 PM" in message.body
    assert "4:40" not in message.body


def test_the_message_layer_sends_nothing_itself():
    """
    Pure, so the privacy rule above is testable to the character. SMTP,
    attachments and retries stay in `email_service.py`, which cannot be tested
    without a mail server -- and a rule that can only be checked with a mail
    server is a rule that stops being checked.
    """
    source = GUARDIAN.read_text(encoding="utf-8")
    for forbidden in ("smtplib", "EmailMessage", "MIMEMultipart", "httpx", "requests"):
        assert forbidden not in source, f"{forbidden} belongs in the transport, not here"


# ---------------------------------------------------------------------------
# Who sees whose address
# ---------------------------------------------------------------------------
# `full_sos` mails somebody's entire emergency contact list. Before JG3 every
# recipient was put in `To`, so a brother, an employer and a neighbour would
# each learn the other two's email addresses because she was late home. The SOS
# path had the same bug and the same fix.

EMAIL_SERVICE = BACKEND / "app" / "services" / "email_service.py"


def _code_only(source: str) -> str:
    """
    Source with comments and docstrings removed.

    Necessary rather than fastidious. This codebase explains itself at length,
    and the comment describing a fix usually *quotes the bug* -- so a naive
    `"msg['To'] = ..." not in source` matches the comment saying that line was
    removed, and passes or fails for the wrong reason. Four tests in this file
    did exactly that before this helper existed.

    The same lesson as `test_journey_deadline.py::_endpoint_sql`, which extracts
    only the SQL literals for the same reason.

    **It strips the SQL too**, because a `text(...)` literal is itself
    triple-quoted -- so anything asserting on query text must use
    `_endpoint_sql_of` instead. That cost one test here as well.
    """
    without_docstrings = re.sub(r'"""(?:.|\n)*?"""', "", source)
    return re.sub(r"#[^\n]*", "", without_docstrings)


def _body_of(name: str) -> str:
    """The code of one function, comments and docstring stripped."""
    code = _code_only(EMAIL_SERVICE.read_text(encoding="utf-8"))
    start = code.index(f"def {name}")
    rest = code[start + 1 :]
    end = rest.index("\n    def ") if "\n    def " in rest else len(rest)
    return rest[:end]


def _addressed(recipients: list[str]) -> MIMEMultipart:
    from app.services.email_service import EmailService

    message = MIMEMultipart("mixed")
    message["From"] = "meridian@example.com"
    # A real instance: `_address` reads `self.from_email`, and `__new__` without
    # `__init__` leaves it unset. Constructing it only reads settings -- nothing
    # connects until `_send_blocking`.
    EmailService()._address(message, recipients)
    return message


def test_one_recipient_is_addressed_directly():
    """
    Their own address, in `To`. A message addressed to nobody looks like bulk
    mail to the reader and to the filter, and this is the common case -- one
    guardian.
    """
    message = _addressed(["brother@example.com"])
    assert message["To"] == "brother@example.com"
    assert message["Bcc"] is None


def test_several_recipients_cannot_see_each_other():
    message = _addressed(["a@example.com", "b@example.com", "c@example.com"])
    assert message["Bcc"] == "a@example.com, b@example.com, c@example.com"
    for address in ("a@example.com", "b@example.com", "c@example.com"):
        assert address not in (message["To"] or ""), "recipients are visible to each other"


def test_the_sos_path_got_the_same_fix():
    """
    The bug predates JG3 and lives in `send_sos_alert`. Fixing only the new
    code path would leave the older, more sensitive one leaking.
    """
    code = _code_only(EMAIL_SERVICE.read_text(encoding="utf-8"))
    assert "msg['To'] = ', '.join(to_emails)" not in code
    assert 'msg["To"] = ", ".join(to_emails)' not in code
    # Both senders go through the one helper.
    assert code.count("self._address(msg, to_emails)") == 2


def test_a_journey_message_is_not_shaped_like_an_emergency():
    """
    `send_guardian_message` is its own method rather than `send_sos_alert` with
    different words: that one is subject-lined "EMERGENCY", builds an HTML part
    styled for an emergency, and carries a video. Two emergency-shaped emails a
    night get filtered, and then the one that matters is in a folder nobody
    opens.
    """
    body = _body_of("send_guardian_message")
    assert "EMERGENCY" not in body
    assert "video" not in body.lower()
    assert "_sos_html" not in body


def test_the_transport_does_not_decide_what_the_message_says():
    """
    `send_guardian_message` takes a subject and a body. If it ever composed one
    itself, the rule that only an escalation may carry a location would have a
    second home -- and `app/journeys/guardian.py`'s tests would no longer be
    testing the thing that is actually sent.
    """
    body = _body_of("send_guardian_message")
    for leak in ("latitude", "longitude", "maps.google", "last seen"):
        assert leak not in body.lower(), f"{leak!r} is composed in the transport"


def test_a_failed_send_does_not_stop_the_sweep():
    """
    The caller is the minute sweep. An agent that raises on one bad address
    stops escalating every other journey in the same run.
    """
    body = _body_of("send_guardian_message")
    assert "return False" in body
    assert "raise" not in body


# ---------------------------------------------------------------------------
# Naming a guardian at start
# ---------------------------------------------------------------------------

ENDPOINT = BACKEND / "app" / "api" / "v1" / "endpoints" / "journeys.py"


def _endpoint_code() -> str:
    return _code_only(ENDPOINT.read_text(encoding="utf-8"))


def _endpoint_sql_of(path: Path) -> str:
    """
    Only the SQL literals from a module, concatenated.

    The same idiom as `test_journey_deadline.py::_endpoint_sql`, and necessary
    for the same reason: a Python keyword argument named after a column --
    `guardian_contact_id=row.guardian_contact_id` in a response builder -- looks
    exactly like an assignment to a regex scanning the whole file, and a test
    that counts writes would fail on it.
    """
    blocks = re.findall(r'text\(\s*f?"""(.*?)"""', path.read_text(encoding="utf-8"), re.S)
    return chr(10).join(blocks)


def test_a_guardian_is_optional_and_defaults_to_nobody():
    """
    Silently emailing whoever is first in somebody's contact list because they
    pressed Start is a surprise that cannot be taken back -- the message has
    already arrived. A journey nobody is told about is JG2's behaviour, which
    works, so the safe default needs no explanation.
    """
    field = JourneyStart.model_fields["guardian_contact_id"]
    assert field.default is None
    assert not field.is_required()


def test_a_contact_id_is_checked_against_the_callers_own_contacts():
    """
    The check that stops Meridian emailing a stranger.

    A contact id is a uuid in a request body. Without `user_id` in the WHERE, a
    request could name a row belonging to any other account, and that person
    gets an email about a journey they have nothing to do with, on behalf of
    somebody they have never met. They cannot tell it was not genuine and it
    cannot be recalled.
    """
    # The SQL, not the code: `_code_only` strips every triple-quoted string,
    # and in this module that includes the `text("""...""")` literals.
    sql = _endpoint_sql_of(ENDPOINT)
    assert "from public.emergency_contacts" in sql
    lookup = sql[sql.index("from public.emergency_contacts") :]
    lookup = lookup[: lookup.index("insert into public.journeys")]
    assert "user_id = :user_id" in lookup, (
        "the contact lookup does not scope to the caller, so any account's "
        "contact could be named as a guardian"
    )


def test_the_foreign_key_is_not_mistaken_for_the_ownership_check():
    """
    `journeys_guardian_contact_fk` proves the row exists. It does not prove it
    belongs to the caller, and "exists" is not the question that matters.
    """
    assert "journeys_guardian_contact_fk" in _migration()
    code = _endpoint_code()
    # The lookup happens before the insert, in that order, in the handler.
    assert code.index("_CONTACT_IS_MINE,") < code.index("_INSERT,")


def test_an_unknown_contact_is_refused_rather_than_dropped():
    """
    Quietly starting the journey with no guardian would hide a client bug and
    reward an attempt -- and in the bug case the person believes somebody is
    watching when nobody is, which is worse than being told it failed.
    """
    code = _endpoint_code()
    guard = code[code.index("_CONTACT_IS_MINE,") : code.index("_INSERT,")]
    assert "HTTP_404_NOT_FOUND" in guard
    assert "raise HTTPException" in guard


def test_a_contact_with_no_email_cannot_be_a_guardian():
    """
    JG3 tells people by email. Accepting a phone-only contact would produce a
    journey that believes somebody is being told while every send fails
    silently inside the sweep -- the worst kind of failure for this feature,
    because it looks exactly like success.
    """
    code = _endpoint_code()
    guard = code[code.index("_CONTACT_IS_MINE,") : code.index("_INSERT,")]
    assert "contact.email" in guard
    assert "HTTP_422_UNPROCESSABLE_ENTITY" in guard


def test_the_contact_is_read_once_for_both_the_check_and_the_address():
    """
    `_CONTACT_IS_MINE` returns name and email alongside the id. Looking the
    contact up twice -- once to validate, once to address -- is how a journey
    gets validated against one contact and mailed to another.
    """
    sql = ENDPOINT.read_text(encoding="utf-8")
    lookup = sql[sql.index("_CONTACT_IS_MINE") : sql.index("_INSERT")]
    assert "select id, name, email" in lookup


def test_the_guardian_is_written_once_and_never_updated():
    """
    It is the record of a choice made at start. A later write would mean a
    journey's guardian could change under the person who is already being
    told about it.
    """
    sql = _endpoint_sql_of(ENDPOINT)
    assert not re.search(r"guardian_contact_id\s*=", sql), (
        "something assigns to guardian_contact_id"
    )
    assert ":guardian_contact_id" in sql


# ---------------------------------------------------------------------------
# The messages name a person, not a gender
# ---------------------------------------------------------------------------

AGENT = BACKEND / "app" / "agents" / "journey_watch.py"

_GENDERED = re.compile(
    r"\b(she|her|hers|he|him|his)\b", re.IGNORECASE
)


def test_no_message_assumes_the_travellers_gender():
    """
    Caught on the first real render: *"She should arrive by about 8:45 PM."*

    `JOURNEY_GUARDIAN.md` tells its story through Rina, so the prose throughout
    this project says "she" -- and that leaked into the rendered strings, where
    it stops being a narrative device and becomes a claim about a specific
    person. Meridian's accounts are not all women, and a safety email that
    misgenders the person it is about is both wrong and the kind of wrong a
    guardian notices immediately.

    Only the rendered output is checked. The docstrings may keep telling Rina's
    story; they are not sent to anybody.
    """
    rendered = [
        started_message(traveller="Rahim", destination="Mirpur", due_by=_DUE),
        arrived_message(traveller="Rahim", at=_DUE),
        escalation_message(
            traveller="Rahim", destination="Mirpur", started_at=_DUE, last_seen=_HERE
        ),
        escalation_message(
            traveller="Rahim",
            destination="Mirpur",
            started_at=_DUE,
            last_seen=None,
        ),
    ]
    for message in rendered:
        for text_part in (message.subject, message.body, message.html):
            found = _GENDERED.findall(text_part)
            assert not found, f"{found} in: {text_part}"


# ---------------------------------------------------------------------------
# The HTML half
# ---------------------------------------------------------------------------


def _messages() -> list[GuardianMessage]:
    """One of each, including all three escalation branches."""
    return [
        started_message(traveller="Rina", destination="Mirpur", due_by=_DUE),
        arrived_message(traveller="Rina", at=_DUE),
        escalation_message(
            traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
        ),
        escalation_message(
            traveller="Rina",
            destination="Mirpur",
            started_at=_DUE,
            last_seen=None,
            started_from=_START,
        ),
        escalation_message(
            traveller="Rina",
            destination="Mirpur",
            started_at=_DUE,
            last_seen=None,
            started_from=None,
        ),
    ]


def test_every_message_has_both_halves():
    """
    A `multipart/alternative` with an empty part is a blank email to whichever
    client prefers that part, and the client that prefers plain text is the
    cheap handset this product is for.
    """
    for message in _messages():
        assert message.body.strip()
        assert message.html.startswith("<!DOCTYPE html>")
        assert message.html.rstrip().endswith("</html>")


def test_a_name_cannot_put_markup_in_the_email():
    """
    The names reaching these templates are typed by users: a traveller's display
    name and a `destination_label` that may be a POI name from a map tap. In the
    plain half that is harmless; in HTML an unescaped `<` is at best a broken
    message and at worst a mail client rendering somebody's input as markup.

    `_oneline` already collapses newlines -- a different rule, for the subject
    header -- and it would not have caught this.
    """
    nasty = '<script>alert("x")</script> & "friends"'
    for message in (
        started_message(traveller=nasty, destination=nasty, due_by=_DUE),
        arrived_message(traveller=nasty, at=_DUE),
        escalation_message(
            traveller=nasty, destination=nasty, started_at=_DUE, last_seen=_HERE
        ),
    ):
        assert "<script>" not in message.html
        assert "&lt;script&gt;" in message.html
        # Escaped, not stripped: the reader should still see the name they know.
        assert "friends" in message.html


def test_the_escalation_offers_its_map_as_a_button():
    """
    The SOS mail's hardest-won lesson, inherited rather than rediscovered: the
    action goes above the coordinates, because nobody reading this needs to read
    a number before they need a map. The colour is stated on a `<span>` inside
    the link for the same reason it is there -- Gmail recolours `<a>` text, and
    the version that did not do this rendered as dark blue on near-black.
    """
    message = escalation_message(
        traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
    )
    html = message.html
    assert "Open this location on a map" in html
    assert _maps_url_of(_HERE) in html
    assert html.index("Open this location on a map") < html.index("Last reported")
    assert 'color:#ffffff;">Open this location on a map' in html


def test_the_fallback_is_not_labelled_as_a_sighting_in_the_layout():
    """
    The same rule the plain half is tested for, in the half that is actually
    read. A box headed "Last reported position" holding the start of the route
    sends somebody to the wrong end of it; the wording is only half the defence,
    because a reader skims headings.
    """
    message = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=None,
        started_from=_START,
    )
    assert "Started from" in message.html
    assert "Last reported" not in message.html
    assert "not a sighting" in message.html


def test_the_empty_escalation_offers_no_map_button():
    """
    No point, no button. A map link to nowhere is worse than none: it is the one
    thing in the message a frightened person will tap first.
    """
    message = escalation_message(
        traveller="Rina",
        destination="Mirpur",
        started_at=_DUE,
        last_seen=None,
        started_from=None,
    )
    assert "Open this location on a map" not in message.html
    assert "maps" not in message.html.lower()
    assert "nowhere to point you" in message.html


def test_the_layout_needs_nothing_a_mail_client_strips():
    """
    Gmail strips most of a `<style>` block and supports no `display:grid`, so a
    layout that depends on either arrives as whatever the fallback looks like.
    `email_service.py` paid for this discovery once; this is the rule, enforced,
    so the next template does not pay again.
    """
    # Code only: the comment above `_shell` names every one of these in order
    # to warn about it, which is the whole reason this rule is written down.
    source = _code_only(GUARDIAN.read_text(encoding="utf-8"))
    for forbidden in ("<style", "display:grid", "display: grid", "flex", "@media"):
        assert forbidden not in source, forbidden
    for message in _messages():
        assert "<style" not in message.html


def test_both_halves_of_the_escalation_agree_on_the_coordinate():
    """
    Two renderings of one fact is two chances to print a different number. The
    pair is built from one `Position`, and this is what says so.
    """
    for point, message in (
        (
            _HERE,
            escalation_message(
                traveller="Rina", destination="Mirpur", started_at=_DUE, last_seen=_HERE
            ),
        ),
        (
            _START,
            escalation_message(
                traveller="Rina",
                destination="Mirpur",
                started_at=_DUE,
                last_seen=None,
                started_from=_START,
            ),
        ),
    ):
        coords = f"{point.latitude:.5f}, {point.longitude:.5f}"
        assert coords in message.body
        assert coords in message.html


def test_the_transport_sends_both_parts_in_the_right_order():
    """
    `multipart/alternative` is ordered least-preferred to most, so the plain
    part goes first. Reversed, a client that can render HTML is shown the text
    one -- which is not a crash, just the styling silently never arriving.
    """
    body = _body_of("send_guardian_message")
    assert 'MIMEMultipart("alternative")' in body
    assert body.index('MIMEText(body, "plain"') < body.index('MIMEText(html, "html"')


def _maps_url_of(position: Position) -> str:
    """The link as `guardian.py` builds it, full precision."""
    return (
        "https://www.google.com/maps/search/?api=1&query="
        f"{position.latitude},{position.longitude}"
    )


# ---------------------------------------------------------------------------
# The sweep's two notice branches
# ---------------------------------------------------------------------------


def _agent_sql() -> str:
    """
    Every SQL statement the sweep holds, fully interpolated.

    Read off the module's compiled `TextClause` objects rather than scraped out
    of the source with a regex. The notice queries are f-strings that splice in
    `_GUARDIAN_FOR` and `_TRAVELLER`, so the source literal contains
    `{_GUARDIAN_FOR}` and not the joins -- and four tests here asserted against
    that placeholder before this was fixed. `.text` is what will actually reach
    Postgres, which is the thing worth asserting on.
    """
    from sqlalchemy.sql.elements import TextClause

    import app.agents.journey_watch as agent

    return chr(10).join(
        value.text
        for name, value in vars(agent).items()
        if isinstance(value, TextClause) and name.startswith("_")
    )


def test_no_notice_can_reach_anybody_elses_contacts():
    """
    The question this exists to answer: *does an escalation email everybody on
    the platform?*

    It cannot, and here is the whole reason. There are exactly two statements in
    the sweep that read `emergency_contacts`, and each is scoped a different
    way:

    * the notice queries join **one** row, `c.id = j.guardian_contact_id`, and
      the endpoint checked that row belonged to the caller before it was stored
      (`test_the_contact_lookup_is_scoped_to_the_caller`);
    * the full-SOS fan-out filters `where user_id = :user_id`, the journey's own
      owner, taken from the escalating UPDATE's `returning`.

    Delete that WHERE and the top rung mails every contact row in the database:
    a stranger's brother, employer and neighbour, told that somebody they have
    never heard of is missing, with a map. It cannot be recalled and it is the
    single worst thing this product could do by accident -- so the absence of a
    bare `from public.emergency_contacts` is asserted here rather than assumed.
    """
    from sqlalchemy.sql.elements import TextClause

    import app.agents.journey_watch as agent

    # One statement at a time. Joining them and splitting on ";" does not work:
    # these statements carry no terminator, so the whole module reads as a
    # single statement and the first scoped join vouches for every later one.
    # That is exactly what this test did until a mutation run showed it passing
    # while the fan-out's WHERE clause was deleted.
    reads = [
        value.text
        for value in vars(agent).values()
        if isinstance(value, TextClause) and "emergency_contacts" in value.text
    ]
    assert reads, "no statement reads emergency_contacts -- has this moved?"
    for statement in reads:
        tail = statement[statement.index("emergency_contacts") :]
        assert "c.id = j.guardian_contact_id" in tail, (
            f"a read of emergency_contacts that is not the guardian join:\n{statement}"
        )


def test_the_sweep_has_no_way_to_read_a_whole_contact_list():
    """
    Stronger than scoping the fan-out: there is no fan-out.

    The ladder used to end with a rung that mailed every contact the traveller
    had listed, and the query behind it was the only statement in this module
    that could return more than one address. Both are gone, so the sweep now
    has no statement capable of addressing more than one person -- which is a
    rule about the shape of the code, not about remembering a WHERE clause.
    """
    import app.agents.journey_watch as agent

    assert not hasattr(agent, "_ALL_CONTACT_EMAILS")
    assert not hasattr(agent, "_FULL_SOS")
    source = _code_only(AGENT.read_text(encoding="utf-8"))
    assert "everyone" not in source
    # Every read of the table is the one-row join to the named guardian.
    sql = _agent_sql()
    assert sql.count("emergency_contacts") == sql.count(
        "c.id = j.guardian_contact_id"
    ), "a read of emergency_contacts that is not the guardian join"


def test_more_than_one_recipient_is_blind_copied():
    """
    The full-SOS ring mails somebody's whole list. On `To`, a brother, an
    employer and a neighbour learn each other's addresses because she was late
    home -- disclosure the feature never asked for and cannot undo.
    """
    body = _body_of("_address")
    assert 'msg["Bcc"] = ", ".join(to_emails)' in body
    assert 'msg["To"] = ", ".join(to_emails)' not in body


def test_a_cancelled_journey_tells_nobody():
    """
    `state = 'arrived'`, never "ended". A cancelled journey gets no message,
    and that is a decision: `cancel` is what leaving route mode calls, so a
    notice here would fire every time somebody closed the route card.

    It is also honest. JG2 and JG3 exist to separate "got there" from "stopped
    telling us", and a cancelled journey is neither -- it is "stopped on
    purpose", which needs nobody.
    """
    sql = _agent_sql()
    arrived = sql[sql.index("j.arrived_notice_at is null") - 400 :]
    arrived = arrived[: arrived.index("limit 200") + 9]
    assert "j.state = 'arrived'" in arrived
    assert "cancelled" not in arrived


def test_a_notice_is_only_sent_once():
    """
    `is null` in the SELECT *and* in the UPDATE. Two overlapping sweeps would
    otherwise both find the row and both email the guardian, and a duplicate
    "she has started a journey" is the most effective way to teach somebody
    that these messages are noise.
    """
    sql = _agent_sql()
    assert sql.count("started_notice_at is null") >= 2
    assert sql.count("arrived_notice_at is null") >= 2


def test_a_stale_journey_never_gets_a_notice():
    """
    Without a bound, the first sweep after an outage emails guardians about
    journeys from days ago -- and a backlog of them at once, which is how a
    guardian learns to filter Meridian. A late "she set off" is misinformation,
    not information.
    """
    from app.agents.journey_watch import NOTICE_BACKLOG

    assert NOTICE_BACKLOG.total_seconds() > 0
    sql = _agent_sql()
    assert sql.count(":backlog_cutoff") == 2


def test_a_guardian_with_no_email_is_skipped_not_retried():
    """
    The endpoint refuses a guardian with no email at the moment of choosing, but
    a contact can be edited afterwards. A sweep that selected a blank address
    would try, fail, and retry it every minute for the whole backlog window.
    """
    sql = _agent_sql()
    assert sql.count("coalesce(trim(c.email), '') <> ''") == 2


def test_the_notices_read_the_real_user_table():
    """
    `auth.users`, not `public.users`.

    The mirror is a table one teammate dropped in `20261015160000`, that
    `Base.metadata.create_all` recreates empty on every app start, and that
    `POST /sos` repopulates one row at a time -- so what is in it is whatever
    those three forces last agreed on. A guardian email addressed from it would
    say "null" or nothing.
    """
    sql = _agent_sql()
    assert "join auth.users" in sql
    assert "public.users" not in sql


def test_a_guardianless_journey_is_not_selected():
    """
    The join to `emergency_contacts` is an inner join, so a journey with a NULL
    guardian cannot appear. That is the private case working: the deadline and
    the check-in still run and nobody is told.
    """
    sql = _agent_sql()
    assert "join public.emergency_contacts c on c.id = j.guardian_contact_id" in sql
    assert "left join public.emergency_contacts" not in sql


def test_a_second_question_clears_the_first_answer():
    """
    The JG2 bug JG3's first dry run found, on a real row.

    `journeys_answered_after_asked` requires `answered_at >= check_in_sent_at`.
    Moving `check_in_sent_at` forward for a second question while leaving the
    first question's answer behind it violates that -- so a journey that had
    been answered once could never be asked again, and the sweep raised an
    IntegrityError every minute for the rest of the trip.

    JG2 intended the opposite: `ESCALATION_TRANSITIONS` is a cycle precisely so
    a journey that runs long is asked again, and `docs/walkthroughs/JG2.md` has
    answering at step 10 and being asked again at step 16. No fixture had a
    journey that had actually been answered, so nothing caught it.
    """
    sql = _agent_sql()
    mark = sql[sql.index("set escalation_state = 'check_in_sent'") :]
    mark = mark[: mark.index("where journey_id")]
    assert re.search(r"\bunanswered_at = null", mark)
    # `(?<!un)` because "answered_at = null" is a SUBSTRING of
    # "unanswered_at = null" -- so a plain `in` check passes on a statement that
    # clears only the non-response, which is exactly the bug. Found by mutating
    # the fix away and watching this test pass anyway.
    assert re.search(r"(?<!un)\banswered_at = null", mark), (
        "a second check-in leaves the previous answer in place, which violates "
        "journeys_answered_after_asked and makes the journey un-askable"
    )


# ---------------------------------------------------------------------------
# The position: collected only for a journey somebody is watching
# ---------------------------------------------------------------------------
# JG2 stored no position at all, and `test_the_heartbeat_carries_no_position`
# held that line with an argument that named its own expiry: the only reader
# would be the escalation JG3 sends to somebody else. JG3 is that reader, so the
# invariant narrows rather than disappears -- and this is the narrower one.


def test_the_heartbeat_may_carry_a_position_and_need_not():
    """
    Optional in both directions.

    Required would mean a phone that cannot see the sky stops being able to
    report at all -- and then silence, which this feature reads as "something is
    wrong", would be caused by a tall building. Being unable to get a fix is not
    evidence that somebody is late.
    """
    fields = JourneyHeartbeat.model_fields
    assert set(fields) == {"remaining_seconds", "latitude", "longitude"}
    assert fields["latitude"].default is None
    assert fields["longitude"].default is None
    assert fields["remaining_seconds"].is_required()


def test_a_position_is_stored_only_for_a_journey_with_a_guardian():
    """
    **The replacement for JG2's no-position rule, and the whole licence JG3 has
    to store one at all.**

    A journey nobody is being told about stores no position -- not a position
    that happens never to be read. The difference matters because "never read"
    is a property of today's code and one refactor away from being false, while
    "never written" is a property of the row.

    Enforced in the same statement that writes the heartbeat, so there is no
    window and no second code path that could forget.
    """
    sql = _endpoint_sql_of(ENDPOINT)
    heartbeat = sql[sql.index("set last_heartbeat_at = now()") :]
    heartbeat = heartbeat[: heartbeat.index("returning")]
    assert "last_position" in heartbeat
    # Every write of either column is gated on there being a guardian.
    for column in ("last_position", "last_position_at"):
        assignment = heartbeat[heartbeat.index(f"{column} = case") :]
        assignment = assignment[: assignment.index("end")]
        assert "guardian_contact_id is not null" in assignment, (
            f"{column} is written without checking for a guardian, so a journey "
            "nobody is watching would still be tracked"
        )


def test_a_heartbeat_with_no_fix_does_not_erase_the_last_one():
    """
    `coalesce`-style `else last_position`, not an unconditional write.

    Losing the only location an escalation could carry, because one heartbeat
    arrived without a GPS fix, would be a null at the worst possible moment --
    and a moving phone produces fixless heartbeats routinely.
    """
    sql = _endpoint_sql_of(ENDPOINT)
    heartbeat = sql[sql.index("set last_heartbeat_at = now()") :]
    heartbeat = heartbeat[: heartbeat.index("returning")]
    assert "else last_position" in heartbeat
    assert "else last_position_at" in heartbeat
    # `cast(:lat as double precision)` and not `:lat`: without the cast asyncpg
    # cannot infer the parameter's type and refuses to prepare the statement at
    # all, and without the `cast(...)` *form* SQLAlchemy mis-parses `:lat::`.
    # Asserted in the shape that actually runs, since this test was written
    # against the shape that did not.
    assert "cast(:lat as double precision) is not null" in heartbeat


def test_the_position_is_never_read_by_a_calm_notice():
    """
    The end-to-end version of the rule, across the two modules that matter.

    `guardian.py` cannot be passed a position by the started or arrived notices
    -- asserted by signature elsewhere in this file -- and the sweep's notice
    queries must not select one either. A query that fetched it would be one
    edit away from putting it in the wrong email.
    """
    sql = _agent_sql()
    for marker in ("j.started_notice_at is null", "j.arrived_notice_at is null"):
        branch = sql[sql.index(marker) - 500 : sql.index(marker) + 200]
        assert "last_position" not in branch, (
            "a calm notice's query selects the position; only an escalation may "
            "ever see it"
        )


# ---------------------------------------------------------------------------
# The ladder: one rung at a time, each gated on the one below
# ---------------------------------------------------------------------------
# `JOURNEY_GUARDIAN.md` §7, which is the sentence this whole phase is built to
# honour: "Every step past the first requires a recorded non-response with a
# timestamp. It cannot jump to panic."
#
# Checked three ways on purpose -- in the state machine (above), in the
# migration's CHECKs (above), and here in the SQL that does the moving. Any one
# of the three could be right while the system was wrong.


def _rung(from_state: str, to_state: str) -> str:
    """The one escalation statement that moves `from_state` to `to_state`."""
    from app.agents.journey_watch import _escalation_step

    return _escalation_step(from_state, to_state).text


def test_each_rung_requires_the_one_below_it():
    """
    The gate, per rung: the previous ring's timestamp is old enough, and nothing
    has been answered since. Both halves, because one without the other is not a
    non-response -- a question asked four seconds ago is unanswered because
    nobody has had time to answer it.
    """
    for lower, upper in (
        (ESCALATION_CHECK_IN_SENT, ESCALATION_CHECK_IN_REPEATED),
        (ESCALATION_CHECK_IN_REPEATED, ESCALATION_CONTACTS_NOTIFIED),
        (ESCALATION_CONTACTS_NOTIFIED, ESCALATION_FULL_SOS),
    ):
        sql = _rung(lower, upper)
        below = ESCALATION_RECORDED_AT[lower]
        above = ESCALATION_RECORDED_AT[upper]
        assert f"escalation_state = '{lower}'" in sql, f"{upper} does not require {lower}"
        assert f"{below} <= :cutoff" in sql, (
            f"{upper} does not require {below} to be old enough, so it could "
            "fire the instant the ring below it did"
        )
        assert f"answered_at < {below}" in sql, (
            f"{upper} does not check for an answer since {below} -- so a journey "
            "that was answered would keep climbing"
        )
        assert f"{above} is null" in sql, f"{upper} could be applied twice"
        assert "state = 'active'" in sql


def test_no_rung_can_be_reached_from_two_below():
    """
    The specific thing §7 forbids. Each statement names exactly one
    `escalation_state` it will move, so there is no path that skips a ring --
    not even one that happens to be unreachable today.
    """
    for lower, upper in (
        (ESCALATION_CHECK_IN_SENT, ESCALATION_CHECK_IN_REPEATED),
        (ESCALATION_CHECK_IN_REPEATED, ESCALATION_CONTACTS_NOTIFIED),
        (ESCALATION_CONTACTS_NOTIFIED, ESCALATION_FULL_SOS),
    ):
        sql = _rung(lower, upper)
        for other in ESCALATION_STATES:
            if other in (lower, upper):
                continue
            assert f"escalation_state = '{other}'" not in sql


def test_a_new_question_resets_the_escalation_record():
    """
    Found while building the ladder, and it corrects the migration.

    `journeys_repeated_after_asked` requires `check_in_repeated_at >=
    check_in_sent_at`, and the two rules above it say the same thing one rung
    higher. A journey that escalated, was answered, and is now being asked
    again would carry the previous cycle's `check_in_repeated_at` *behind* the
    new `check_in_sent_at` and violate all three -- the same shape as the
    `answered_at` bug, one level up.

    So the five timestamps describe **the outstanding question, not the
    journey's lifetime** -- which is the choice JG2 already made for
    `unanswered_at`, extended to the whole ladder.

    The migration's comment says the opposite ("KEEPS these timestamps,
    because they are the history of what happened on this trip"). It is wrong,
    and the file is applied and checksummed so it cannot be edited; this test
    and the comment in `_MARK_SENT` are the correction. A real lifetime history
    would need the events table JG3 deliberately did not build.
    """
    sql = _agent_sql()
    mark = sql[sql.index("set escalation_state = 'check_in_sent'") :]
    mark = mark[: mark.index("where journey_id")]
    for column in ("check_in_repeated_at", "contacts_notified_at", "full_sos_at"):
        assert f"{column} = null" in mark, (
            f"a new question leaves {column} behind it, which violates the "
            "ordering CHECK and makes the journey un-askable"
        )


def test_only_the_escalation_reads_the_start_point():
    """
    `origin` has been on the table since JG1 and is read all over the app -- it
    is how a route is drawn back on the map. What matters here is that the
    *sweep* reads it in exactly one statement, the same one that reads
    `last_position`, so the start point cannot reach a calm notice by being
    selected alongside something innocent.
    """
    from sqlalchemy.sql.elements import TextClause

    import app.agents.journey_watch as agent

    # One *statement*, not one occurrence -- the same trap as the test below:
    # the column is cast twice, once for the latitude and once for the
    # longitude, so counting substrings says 2 about a single query.
    readers = [
        name
        for name, value in vars(agent).items()
        if isinstance(value, TextClause) and "j.origin" in value.text
    ]
    assert readers == ["_ESCALATION_RECIPIENTS"], (
        f"{readers} read the journey's origin; only the escalation may"
    )


def test_only_the_escalation_reads_a_position():
    """
    One query in the sweep selects `last_position`, and it is the one that feeds
    `escalation_message` -- the only composer with a parameter for it.
    """
    from sqlalchemy.sql.elements import TextClause

    import app.agents.journey_watch as agent

    # One *statement*, not one occurrence: `_ESCALATION_RECIPIENTS` casts the
    # column twice, once for the latitude and once for the longitude.
    readers = [
        name
        for name, value in vars(agent).items()
        if isinstance(value, TextClause) and "last_position" in value.text
    ]
    assert readers == ["_ESCALATION_RECIPIENTS"], (
        f"{readers} read last_position; only the escalation may"
    )


def test_the_last_rung_does_not_reach_the_police():
    """
    `full_sos` emails contacts. 999 and the thana record are JG7, and
    `JOURNEY_GUARDIAN.md` is explicit that reaching this state from an
    unanswered check-in and then contacting police would be the most damaging
    false positive this product can produce.
    """
    source = _code_only(AGENT.read_text(encoding="utf-8"))
    for forbidden in ("police", "thana", "999", "sos_service", "POLICE_ROUTING"):
        assert forbidden not in source, f"{forbidden!r} in the sweep is JG7"


def test_an_escalation_addresses_exactly_one_person():
    """
    The guardian, and nobody else. This replaces a test that checked the last
    ring deduped the guardian out of the contact list it also mailed -- a
    problem that cannot occur now, because the list is never read.

    Asserted on the recipient expression itself: `[detail.guardian_email]` is a
    one-element list by construction, and anything that widened it would have
    to change this line.
    """
    source = _code_only(AGENT.read_text(encoding="utf-8"))
    body = source[source.index("async def _escalate_by_email") :]
    assert "recipients = [detail.guardian_email]" in body
    assert "recipients =" in body and body.count("recipients =") == 1


def test_a_phone_with_no_token_still_climbs():
    """
    A missing push token must not stop the ladder. The thing being escalated is
    the absence of an answer, and somebody with no token is the person least
    likely to produce one -- so treating "no device" as a reason not to escalate
    would exempt exactly the people the feature is for.
    """
    source = _code_only(AGENT.read_text(encoding="utf-8"))
    # The state is moved by the UPDATE before `_push_again` is ever called, so
    # its return value cannot block the climb.
    run = source[source.index("_REPEAT_THE_QUESTION, gate") :]
    run = run[: run.index("_TELL_THE_GUARDIAN")]
    assert "_push_again" in run
    assert "continue" not in run, (
        "the second-ask branch skips rows, which could leave a journey on a "
        "lower rung because of a missing token"
    )


# ---------------------------------------------------------------------------
# What the app can see, and what it is allowed to answer
# ---------------------------------------------------------------------------
# Both of these were real, both were found by running the code rather than by
# reading it, and both were introduced by widening the ladder in steps 1-7
# without widening the two things that face the phone. They are the reason this
# section exists: a state machine is only as wide as its narrowest edge.


def test_an_answer_is_accepted_from_every_rung_of_the_ladder():
    """
    The one that mattered. `_CHECK_IN` gated on `escalation_state =
    'check_in_sent'`, which was right when that was the only state with a
    question outstanding -- and wrong the moment the ladder existed, because
    `_push_again` asks the traveller a second time *in* `check_in_repeated`.

    So the person being asked hardest was the one whose answer was refused with
    a 409, while the sweep carried on to email their contacts and then everyone
    they know. Measured against a row in each state: three of the four answered
    nothing.
    """
    from app.api.v1.endpoints.journeys import _CHECK_IN

    sql = _CHECK_IN.text
    clause = sql[sql.index("escalation_state in (") :]
    clause = clause[: clause.index(")")]
    for state in ESCALATION_LADDER:
        assert f"'{state}'" in clause, (
            f"a journey in {state} cannot be answered, so nothing the traveller "
            "presses will stop the escalation"
        )


def test_an_answer_out_of_nowhere_is_still_refused():
    """
    The other half, and the reason the clause is not simply dropped. An answer
    accepted on a journey in `normal` is a deadline extension bought by
    replaying a notification action, which is the one thing a lock-screen
    button must not be.
    """
    from app.api.v1.endpoints.journeys import _CHECK_IN

    sql = _CHECK_IN.text
    clause = sql[sql.index("escalation_state in (") :]
    clause = clause[: clause.index(")")]
    assert f"'{ESCALATION_NORMAL}'" not in clause


def test_the_answerable_states_are_exactly_the_escalated_ones():
    """
    Built from `ESCALATION_LADDER`, not written out. The set of states a
    journey can be answered out of is by definition the set it can be escalated
    into, and the two drifting apart is precisely how the bug above happened --
    the ladder grew in one file and the answer path stayed behind in another.
    """
    from app.api.v1.endpoints.journeys import _ANSWERABLE

    assert sorted(_ANSWERABLE.replace("'", "").split(", ")) == sorted(ESCALATION_LADDER)


def test_the_app_can_read_a_journey_in_any_state():
    """
    `JourneyResponse.escalation_state` listed two states. Pydantic validates
    responses as well as requests, so the moment a journey escalated,
    `GET /journeys/active` raised a ValidationError and returned a 500: the app
    lost the journey -- the card, the deadline and the answer button -- exactly
    when the feature started working.

    A `Literal` cannot be built from a tuple at type-check time, so the two
    lists are written separately and compared here.
    """
    import typing

    from app.schemas.journey import JourneyResponse

    field = JourneyResponse.model_fields["escalation_state"]
    assert set(typing.get_args(field.annotation)) == set(ESCALATION_STATES)


def test_the_app_can_read_every_timestamp_the_ladder_writes():
    """
    The journey screen's timeline is these columns and nothing else -- JG3
    deliberately built no events table, so a rung the wire cannot carry is a
    rung that never happened as far as the person on the trip is concerned.
    """
    from app.schemas.journey import JourneyResponse

    for state, column in ESCALATION_RECORDED_AT.items():
        assert column in JourneyResponse.model_fields, (
            f"{state} is recorded in {column}, which the app cannot see"
        )


def test_the_columns_the_app_reads_include_the_whole_ladder():
    """
    The wire shape and the query have to agree. `_response` reads these
    attributes off the row, so a column missing from `_COLUMNS` is an
    AttributeError on every journey, not a missing field on some of them.
    """
    from app.api.v1.endpoints.journeys import _COLUMNS

    for column in (
        *ESCALATION_RECORDED_AT.values(),
        "guardian_contact_id",
        "guardian_name",
        "started_notice_at",
        "arrived_notice_at",
    ):
        assert column in _COLUMNS, f"{column} is not selected, so no response can carry it"


def test_the_guardians_name_comes_from_the_server():
    """
    One word on the card -- "Telling Ammu" -- and it comes down with the
    journey rather than being looked up in the app's own contact list.

    Not a preference. The journey this phase exists for is the one the app was
    force-stopped out of; on that cold start the card renders from a single
    `GET /journeys/active` and the contacts have not been fetched. A name
    resolved client-side would be blank on exactly the journey that matters.
    """
    from app.api.v1.endpoints.journeys import _COLUMNS

    assert "from public.emergency_contacts c" in _COLUMNS
    assert "as guardian_name" in _COLUMNS
