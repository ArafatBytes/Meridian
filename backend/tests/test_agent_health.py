"""
B9 — the fleet health state machine, and the one rule it must not break.

`app/agents/health.py` answers "is this agent working". Two callers act on that
answer: an operator reading `python -m app.agents status`, and a user reading a
badge on a screen. Both of them stop checking when it says yes.

So the tests that matter here are the ones that try to make it say yes wrongly:
a run stuck at `running` that *sounds* like progress, a cadence it cannot parse,
an agent that has never run at all. Each of those must come back as something
other than `working`.

Everything is a pure function or a source scan — no database, matching the rest
of this suite. `fleet_health` itself is driven through a recording stub, which
is what lets the defect-57 regression below exist without Postgres.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.health import (
    LATE_GRACE,
    MISSED_CYCLES_BEFORE_LATE,
    AgentHealth,
    _decode_errors,
    _state,
    cadence_of,
    format_age,
    format_fleet,
    worst_state,
)
from app.agents.registry import STALE_RUN, agents
from app.contracts.agents import AgentHealthReport

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _health(**overrides: object) -> AgentHealth:
    """An otherwise-healthy agent, so each test states only what it is about."""
    base = {
        "agent": "live_risk",
        "cron": "*/15 * * * *",
        "cadence": timedelta(minutes=15),
        "state": "working",
        "last_started_at": NOW - timedelta(minutes=2),
        "last_finished_at": NOW - timedelta(minutes=1),
        "last_status": "ok",
        "age": timedelta(minutes=2),
        "overdue_by": None,
        "items_in": 6,
        "items_out": 2,
        "errors": (),
        "runs_24h": 96,
        "failures_24h": 0,
    }
    base.update(overrides)
    return AgentHealth(**base)  # type: ignore[arg-type]


# ===========================================================================
# The state machine
# ===========================================================================


def test_a_fresh_successful_run_is_working() -> None:
    state, overdue = _state(cadence=timedelta(minutes=15), last_status="ok", age=timedelta(minutes=2))
    assert (state, overdue) == ("working", None)


def test_partial_is_working_and_not_a_problem() -> None:
    """
    `contracts/agents.py` is explicit about this: three news sources, one is
    down, the run still produced flags. Collapsing `partial` into failed "would
    mean the fleet looks broken whenever any publisher has a bad day" — and a
    fleet that is always amber is a fleet nobody reads.
    """
    state, _ = _state(cadence=timedelta(minutes=15), last_status="partial", age=timedelta(minutes=2))
    assert state == "working"


def test_a_failed_run_is_a_problem() -> None:
    state, _ = _state(cadence=timedelta(minutes=15), last_status="failed", age=timedelta(minutes=2))
    assert state == "problem"


def test_a_run_still_inside_the_stale_window_is_mid_run_not_broken() -> None:
    state, _ = _state(cadence=timedelta(minutes=15), last_status="running", age=STALE_RUN / 2)
    assert state == "working"


def test_a_run_stuck_past_the_stale_window_is_a_problem() -> None:
    """
    The failure this whole module was written for, named in two places in the
    codebase before it had a reader. A crashed container does not leave a
    `failed` row — it leaves a row that still claims to be running, for ever.
    `running` is the one status that must not be read as good news on age alone.
    """
    state, _ = _state(
        cadence=timedelta(minutes=15),
        last_status="running",
        age=STALE_RUN + timedelta(minutes=1),
    )
    assert state == "problem"


def test_an_agent_that_has_never_run_says_so() -> None:
    assert _state(cadence=timedelta(minutes=15), last_status=None, age=None)[0] == "never_run"


def test_two_missed_cycles_is_still_working_and_the_third_is_late() -> None:
    cadence = timedelta(minutes=15)
    allowed = cadence * MISSED_CYCLES_BEFORE_LATE + LATE_GRACE

    inside, _ = _state(cadence=cadence, last_status="ok", age=allowed - timedelta(seconds=1))
    assert inside == "working"

    outside, overdue = _state(cadence=cadence, last_status="ok", age=allowed + timedelta(minutes=5))
    assert outside == "late"
    assert overdue == timedelta(minutes=5)


def test_an_unparseable_cadence_claims_nothing() -> None:
    """
    Not `working`, which would be a guess in the optimistic direction. An agent
    whose schedule this module cannot read is one an operator has to look at.
    """
    state, _ = _state(cadence=None, last_status="ok", age=timedelta(days=3))
    assert state == "unknown"


def test_a_stale_success_can_never_report_working() -> None:
    """
    The rule in the module docstring, asserted directly: *never report healthy
    when the answer is stale*. A green badge over fourteen-hour-old risk data is
    worse than no badge, because a user who has been told the system works will
    trust the map. Swept across every cadence in use.
    """
    for cadence in (timedelta(minutes=1), timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1)):
        state, _ = _state(cadence=cadence, last_status="ok", age=timedelta(hours=14))
        assert state == "late", f"{cadence} reported {state} on a 14-hour-old run"


# ===========================================================================
# Cadence parsing
# ===========================================================================


@pytest.mark.parametrize(
    ("cron", "expected"),
    [
        ("* * * * *", timedelta(minutes=1)),
        ("*/15 * * * *", timedelta(minutes=15)),
        ("*/30 * * * *", timedelta(minutes=30)),
        ("17 * * * *", timedelta(hours=1)),
        ("20 * * * *", timedelta(hours=1)),
        ("30 3 * * *", timedelta(days=1)),
        ("0 */6 * * *", timedelta(hours=6)),
    ],
)
def test_cadence_of_reads_the_shapes_in_use(cron: str, expected: timedelta) -> None:
    assert cadence_of(cron) == expected


@pytest.mark.parametrize(
    "cron",
    [
        None,
        "",
        "not a cron",
        "* * * * * *",  # six fields
        "0 0 * * 1",  # weekly — deliberately not guessed
        "0 0 1 * *",  # monthly
        "*/0 * * * *",  # a zero step is not a cadence
    ],
)
def test_cadence_of_refuses_to_guess(cron: str | None) -> None:
    """
    `croniter` is not a dependency, and a wrongly-guessed interval produces
    either a false `late` badge or a missed one. `None` here surfaces as
    `unknown`, which asks a human instead of inventing an answer.
    """
    assert cadence_of(cron) is None


def test_every_registered_agent_has_a_cadence_this_module_can_read() -> None:
    """
    The coupling that keeps the fleet view honest as agents are added. If someone
    registers an agent on a weekly cron, `cadence_of` returns None, the card says
    `unknown`, and nothing else complains — this test is the thing that
    complains, and it names the function to teach.
    """
    unreadable = {
        name: agent.cron
        for name, agent in agents().items()
        if agent.cron and cadence_of(agent.cron) is None
    }
    assert unreadable == {}, (
        f"these agents have cron shapes `cadence_of()` cannot read: {unreadable}. "
        "Their fleet cards will say `unknown` rather than working or late. Teach "
        "`app/agents/health.py :: cadence_of` the shape."
    )


def test_an_agent_with_no_cron_is_not_treated_as_scheduled() -> None:
    """
    `BaseAgent.cron` defaults to None, so a library module or an on-demand agent
    must not be judged late for never being scheduled.
    """
    assert cadence_of(None) is None
    assert _state(cadence=None, last_status="ok", age=timedelta(days=30))[0] == "unknown"


# ===========================================================================
# Reading the errors column back
# ===========================================================================


def test_errors_decode_from_the_text_cast() -> None:
    assert _decode_errors('["boom", "bang"]') == ("boom", "bang")
    assert _decode_errors("[]") == ()


@pytest.mark.parametrize("raw", [None, "", "not json", '{"not": "a list"}', "null"])
def test_a_broken_errors_payload_does_not_take_the_fleet_view_down(raw: str | None) -> None:
    """
    The run's `status` already said it failed, and that is what a reader acts on.
    Losing the error text is a worse readout; raising would mean one malformed
    row hides the health of all five agents.
    """
    assert _decode_errors(raw) == ()


# ===========================================================================
# The operator's readout
# ===========================================================================


@pytest.mark.parametrize(
    ("span", "expected"),
    [
        (None, "never"),
        (timedelta(seconds=3), "just now"),
        (timedelta(seconds=45), "45s"),
        (timedelta(minutes=4), "4m"),
        (timedelta(hours=3, minutes=12), "3h 12m"),
        (timedelta(days=2, hours=4), "2d 4h"),
    ],
)
def test_format_age_is_coarse_where_precision_says_nothing(span: timedelta | None, expected: str) -> None:
    assert format_age(span) == expected


def test_a_stuck_run_is_called_out_in_words_not_just_a_column() -> None:
    stuck = _health(
        agent="scheduled_risk",
        last_status="running",
        age=STALE_RUN + timedelta(hours=2),
        state="problem",
    )
    out = format_fleet([stuck])
    assert "STUCK" in out
    assert "scheduled_risk" in out
    # The operator's next action has to be in the text: nothing retries this.
    assert "retry" in out.lower()


def test_a_late_agent_points_at_beat_rather_than_the_agent() -> None:
    """
    The diagnosis that is easy to get wrong. A beat container that is not running
    produces a late agent with no errors anywhere, because the agent is not
    failing — it is not being asked.
    """
    late = _health(state="late", last_status="ok", overdue_by=timedelta(hours=2))
    out = format_fleet([late])
    assert "LATE" in out
    assert "beat" in out


def test_the_operator_readout_shows_error_text() -> None:
    out = format_fleet([_health(state="problem", last_status="failed", errors=("DBAPIError: boom",))])
    assert "DBAPIError: boom" in out


def test_an_empty_fleet_explains_itself_rather_than_printing_a_blank_table() -> None:
    out = format_fleet([])
    # `CADENCE` and `STATE` appear only in the table header, so their absence is
    # the test that no empty table was printed. `AGENT` is not usable for that:
    # the explanation itself names the `AGENT = ...` line whose absence causes it.
    assert "CADENCE" not in out
    assert "STATE" not in out
    assert "AGENT = " in out


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ((), "working"),
        (("working", "working"), "working"),
        (("working", "late"), "late"),
        (("late", "problem"), "problem"),
        (("working", "never_run"), "working"),
        (("working", "unknown"), "working"),
    ],
)
def test_worst_state_drives_a_usable_exit_code(states: tuple[str, ...], expected: str) -> None:
    """
    `never_run` and `unknown` must not make a shell health check fail: the first
    is the normal state of a fresh database, the second is this module declining
    to guess. Neither is evidence that anything is wrong.
    """
    assert worst_state([_health(state=state) for state in states]) == expected


# ===========================================================================
# What the API is allowed to say
# ===========================================================================

_OPERATOR_ONLY = {"errors", "items_in", "items_out", "failures_24h", "last_status", "cron"}


def test_the_user_facing_contract_carries_no_operator_fields() -> None:
    """
    The split this feature is built on. An error string is a Python exception
    repr — noise to a user and a small amount of help to anyone probing the
    deployment. `items_in`/`items_out` do not mean the same thing across agents,
    so one column of them invites an invalid comparison. `failures_24h` is
    alarming without being actionable, because a user cannot retry an agent.

    If one of these ever needs to be shown, that is a product decision and this
    test is where it gets made deliberately rather than by an autocomplete.
    """
    leaked = _OPERATOR_ONLY & set(AgentHealthReport.model_fields)
    assert leaked == set(), (
        f"AgentHealthReport now exposes operator-only fields: {sorted(leaked)}. "
        "These stay in `python -m app.agents status`, where the reader can act "
        "on them — see the contract's own docstring for why each one is out."
    )


def test_the_user_facing_contract_still_carries_what_the_screen_needs() -> None:
    """The mirror of the test above: narrowing it to nothing is also a failure."""
    assert {
        "agent",
        "state",
        "last_run_at",
        "seconds_since_last_run",
        "cadence_seconds",
        "runs_last_24h",
    } <= set(AgentHealthReport.model_fields)


def test_the_endpoint_requires_a_signed_in_caller() -> None:
    """
    `/ingestion/status` is deliberately open, because *"it describes public news,
    not a user"*. That reason does not carry to this endpoint, which describes
    which parts of our deployment are currently not working. Asserted against
    the source, because the dependency being dropped is a silent change — the
    endpoint would keep working, for everybody.
    """
    source = Path(__file__).resolve().parent.parent / "app" / "api" / "v1" / "endpoints" / "agents.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    handlers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list
    ]
    assert handlers, "no handler found in endpoints/agents.py — did it move?"
    for handler in handlers:
        defaults = [
            default
            for default in handler.args.defaults + [d for d in handler.args.kw_defaults if d]
            if isinstance(default, ast.Call)
        ]
        gated = any(
            isinstance(arg, ast.Name) and arg.id == "get_current_user"
            for call in defaults
            for arg in call.args
        )
        assert gated, (
            f"{handler.name} in endpoints/agents.py has no `get_current_user` "
            "dependency. Fleet health describes the deployment, not public news, "
            "so it is gated — see the module docstring."
        )


# ===========================================================================
# Keeping the client's words in step with the server's agents
# ===========================================================================

_CATALOGUE = Path("frontend") / "src" / "features" / "status" / "agentCatalogue.ts"


def _find_catalogue() -> Path | None:
    """
    Same two environments as the drift check: the repository root on the host,
    and the `api` container where the client files are mounted at `/frontend/...`.
    """
    backend = Path(__file__).resolve().parent.parent
    for root in (backend.parent, Path("/"), Path.cwd(), *Path.cwd().parents):
        candidate = root / _CATALOGUE
        if candidate.is_file():
            return candidate
    return None


CATALOGUE = _find_catalogue()


@pytest.mark.skipif(
    CATALOGUE is None,
    reason=(
        "no frontend/src/features/status/agentCatalogue.ts in this environment "
        "(expected inside the api container via docker-compose.yml's read-only mounts)"
    ),
)
def test_every_registered_agent_has_words_for_a_user() -> None:
    """
    The server decides which agents exist; the client decides what they are
    called. An agent added to the backend with no catalogue entry reaches the
    System Status screen as a prettified key and a sentence saying the app has no
    description for it — honest, and not what anyone intended to ship.

    Only the backend knows the real list, so the check lives here. The client
    half (`agentCatalogue.test.ts`) pins the five names from its own side, so
    this pair fails in both directions: an agent added without words, and words
    added for an agent that does not exist.
    """
    assert CATALOGUE is not None
    source = CATALOGUE.read_text(encoding="utf-8")
    missing = sorted(name for name in agents() if f"\n  {name}: {{" not in source)
    assert missing == [], (
        f"these agents have no entry in agentCatalogue.ts: {missing}. They will "
        "render on the System Status screen with a prettified key and no "
        "description. Add a title and a blurb written from the agent's own "
        "docstring — not from its name, which is how `expiry_sweep` would have "
        "got a description that frightens users about the wrong thing."
    )
