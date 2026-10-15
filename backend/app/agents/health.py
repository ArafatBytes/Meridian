"""
Fleet health — is each agent actually running, and is its answer still current.

B9. One read over `public.agent_runs`, shared by three callers:

    python -m app.agents status      the operator's table, with error text
    GET /api/v1/agents/status        what a signed-in user is shown
    tests/test_agent_health.py       the state machine, fed synthetic rows

## Why this exists

Nothing read `agent_runs` back. Rows have been written since D01 — one per run,
with timings, counts, errors and metrics, indexed on `(agent, started_at desc)`
and on `status` — and the only reader was `/ingestion/status`, which reports the
*one* agent behind the news layer. So if `scheduled_risk` had stopped at 2am, the
way to find out was to notice the map looked wrong.

Both the schema and the registry already wrote down the specific failure this is
for. `registry.STALE_RUN`: *"a container restart mid-run leaves its row at
`running` forever, so that stuck row is exactly what Track B's fleet view should
surface."* A crashed agent does not leave a `failed` row — it leaves a row that
still claims to be working, and claims it indefinitely.

## The one rule this module will not break

**Never report healthy when the answer is stale.** A green badge over
fourteen-hour-old risk data is worse than no badge, because a user who has been
told the system is working will trust the map. Every state below is derived from
a measured age, and an age this module cannot establish becomes `never_run` or
`unknown` rather than optimism.

## Operator detail and user detail are not the same payload

`errors`, `metrics` and raw `items_in`/`items_out` are operator fields and the
API contract does not carry them: an error string is a Python exception
repr, which is noise to a user and a small information leak to anyone else. The
endpoint maps to plain language and a measured age; the CLI prints everything.
That split is the reason this module returns a rich object and lets each caller
narrow it, rather than returning the narrow one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import STALE_RUN, agents

HealthState = Literal["working", "late", "problem", "never_run", "unknown"]
"""
`late` and `problem` are separate because they want different responses. `late`
is "the schedule has slipped" — the last run succeeded and nothing has replaced
it. `problem` is "the last thing we know is that it broke", which covers both a
`failed` row and a row stuck at `running` past `STALE_RUN`.

`unknown` is only for an agent whose cadence this module cannot parse, which is
how a cron shape nobody anticipated degrades: no claim rather than a wrong one.

`partial` is NOT a problem state. `contracts/agents.py` says why: three news
sources and one is down still produces flags, and collapsing that into failed
"would mean the fleet looks broken whenever any publisher has a bad day."
"""

_MINUTE: Final = 60.0
_HOUR: Final = 3600.0

MISSED_CYCLES_BEFORE_LATE: Final = 2.0
"""
How many whole cadences may pass before an agent is `late`, plus the grace below.

Two rather than one, because a run that starts a few seconds after its slot and
takes a minute to finish would otherwise flap between states every cycle. Two
missed cycles is still prompt: `live_risk` runs every 15 minutes, so it is `late`
after 31 minutes, which is well before anyone would have noticed by eye.
"""

LATE_GRACE: Final = timedelta(seconds=60)
"""
Added on top, and it exists for `alert_dispatch`, which runs every minute. Two
cycles of a one-minute agent is two minutes, which is inside the noise of
container scheduling; three is not.
"""


@dataclass(frozen=True)
class AgentHealth:
    """
    One agent's health. Everything here is measured, nothing is assumed.

    `age` and `overdue_by` are `timedelta | None` rather than being flattened to
    seconds, because the caller that formats them (CLI) and the caller that
    serialises them (API) want different units, and a float of unstated unit is
    how one of them ends up a thousand times wrong.
    """

    agent: str
    cron: str | None
    cadence: timedelta | None
    state: HealthState
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_status: str | None
    age: timedelta | None
    overdue_by: timedelta | None
    items_in: int
    items_out: int
    errors: tuple[str, ...]
    runs_24h: int
    failures_24h: int

    @property
    def is_stuck(self) -> bool:
        """
        A row still at `running` after `STALE_RUN`. Operator-only: to a user this
        is just a problem, but to an operator it is a *different* problem from a
        failed run — nothing will retry it, and the registry's overlap guard
        stopped blocking on it, so runs resumed while this row stayed open.
        """
        return self.last_status == "running" and self.age is not None and self.age > STALE_RUN

    @property
    def is_healthy(self) -> bool:
        return self.state == "working"


def cadence_of(cron: str | None) -> timedelta | None:
    """
    How often a cron expression fires, for the shapes this project actually uses.

    Returns `None` for anything it cannot be sure about, and that is the whole
    design: `croniter` is not a dependency, and guessing an interval wrong means
    either a false `late` badge or a missed one. An unparsed cadence surfaces as
    `unknown`, which says "ask the operator" instead of making something up.

    Handled: `* * * * *` (every minute), `*/N * * * *` (every N minutes),
    `M * * * *` (hourly at minute M), `M H * * *` (daily).
    """
    if not cron:
        return None
    parts = cron.split()
    if len(parts) != 5:
        return None
    minute, hour, day_of_month, month, day_of_week = parts
    if (day_of_month, month, day_of_week) != ("*", "*", "*"):
        return None  # weekly/monthly: not in use, and not worth guessing

    if hour == "*":
        if minute == "*":
            return timedelta(seconds=_MINUTE)
        if minute.startswith("*/") and minute[2:].isdigit() and int(minute[2:]) > 0:
            return timedelta(minutes=int(minute[2:]))
        if minute.isdigit():
            return timedelta(seconds=_HOUR)
        return None
    if hour.isdigit() and minute.isdigit():
        return timedelta(days=1)
    if hour.startswith("*/") and hour[2:].isdigit() and int(hour[2:]) > 0 and minute.isdigit():
        return timedelta(hours=int(hour[2:]))
    return None


def _decode_errors(raw: str | None) -> tuple[str, ...]:
    """
    `agent_runs.errors` read back as strings.

    The column is selected as `errors::text` and decoded here rather than relying
    on the driver to hand back a list, which is the same reason
    `/ingestion/status` computes `jsonb_array_length` in SQL: whether asyncpg
    decodes jsonb depends on a codec this project does not register, so a value
    that is a `str` on one path and a `list` on another is a bug waiting for a
    different driver. A payload that will not decode yields no errors rather than
    breaking the whole fleet view — the run's `status` already said it failed,
    and that is the part a reader acts on.
    """
    if not raw:
        return ()
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(str(problem) for problem in decoded)


def _state(
    *,
    cadence: timedelta | None,
    last_status: str | None,
    age: timedelta | None,
) -> tuple[HealthState, timedelta | None]:
    """The state machine, kept separate from the query so tests can drive it directly."""
    if last_status is None or age is None:
        return "never_run", None

    # A row stuck at `running` is the crashed-agent case, and it must not read as
    # mid-run just because `running` sounds like progress.
    if last_status == "running":
        return ("problem", None) if age > STALE_RUN else ("working", None)

    if last_status == "failed":
        return "problem", None

    if cadence is None:
        # `ok`/`partial` but no way to know whether another run was due by now.
        return "unknown", None

    allowed = cadence * MISSED_CYCLES_BEFORE_LATE + LATE_GRACE
    if age > allowed:
        return "late", age - allowed
    return "working", None


async def fleet_health(db: AsyncSession, *, now: datetime | None = None) -> list[AgentHealth]:
    """
    Health for every registered agent, ordered by name.

    Driven by `registry.agents()` and not by what is in the table, so an agent
    that has never run once still appears — as `never_run`, which is the state
    most worth seeing. A view built from `select distinct agent from agent_runs`
    would show nothing at all for the agent that never started, which is the
    opposite of useful.

    `dry_run` rows are excluded throughout: a dry run writes nothing, so counting
    it as evidence of health would mean a test run could make a dead agent look
    alive.
    """
    moment = now or datetime.now(UTC)
    registered = agents()

    latest = {
        row.agent: row
        for row in (
            await db.execute(
                text(
                    "select distinct on (agent) agent, started_at, finished_at, status, "
                    "       items_in, items_out, errors::text as errors_json "
                    "  from public.agent_runs "
                    " where dry_run = false "
                    " order by agent, started_at desc"
                )
            )
        ).all()
    }

    # Counted over the window rather than derived from the latest row: "it is
    # working now" and "it has failed nine times today" are both worth knowing,
    # and only the second one explains a flapping agent.
    counts = {
        row.agent: row
        for row in (
            await db.execute(
                text(
                    "select agent, count(*) as runs, "
                    "       count(*) filter (where status = 'failed') as failures "
                    "  from public.agent_runs "
                    " where dry_run = false and started_at > :since "
                    " group by agent"
                ),
                {"since": moment - timedelta(hours=24)},
            )
        ).all()
    }

    fleet: list[AgentHealth] = []
    for name in sorted(registered):
        cron = registered[name].cron
        cadence = cadence_of(cron)
        row = latest.get(name)
        age = moment - row.started_at if row else None
        state, overdue = _state(
            cadence=cadence,
            last_status=row.status if row else None,
            age=age,
        )
        tally = counts.get(name)
        errors = _decode_errors(row.errors_json) if row else ()
        fleet.append(
            AgentHealth(
                agent=name,
                cron=cron,
                cadence=cadence,
                state=state,
                last_started_at=row.started_at if row else None,
                last_finished_at=row.finished_at if row else None,
                last_status=row.status if row else None,
                age=age,
                overdue_by=overdue,
                items_in=row.items_in if row else 0,
                items_out=row.items_out if row else 0,
                errors=errors,
                runs_24h=int(tally.runs) if tally else 0,
                failures_24h=int(tally.failures) if tally else 0,
            )
        )
    return fleet


# ============================================================================
# The operator's table — `python -m app.agents status`
# ============================================================================

_STATE_MARK: Final = {
    "working": "ok  ",
    "late": "LATE",
    "problem": "FAIL",
    "never_run": "----",
    "unknown": "?   ",
}


def format_age(span: timedelta | None) -> str:
    """
    A duration as an operator reads it: `4m`, `3h 12m`, `2d 4h`, `just now`.

    Deliberately coarse above an hour. The question this answers is "is this
    current", and `13h` settles it; `13h 41m 09s` spends three extra columns
    saying the same thing. Seconds are only shown under a minute, where they are
    the whole of the information.
    """
    if span is None:
        return "never"
    seconds = int(span.total_seconds())
    if seconds < 10:
        return "just now"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < _HOUR:
        return f"{seconds // 60}m"
    if seconds < 86400:
        hours, rest = divmod(seconds, int(_HOUR))
        return f"{hours}h {rest // 60:02d}m"
    days, rest = divmod(seconds, 86400)
    return f"{days}d {rest // int(_HOUR)}h"


def format_fleet(fleet: list[AgentHealth]) -> str:
    """
    The whole operator readout, as one string.

    Returned rather than printed so a test can assert on it — a status command
    whose output nobody checks is how "it looked fine" becomes the only evidence.

    Everything the API withholds is here: error text, item counts, the 24-hour
    failure tally, and the stuck-run distinction. This reader can act on all of
    it; a user cannot.
    """
    if not fleet:
        return (
            "No agents are registered. `registry.agents()` discovers modules under\n"
            "app/agents/ that export `AGENT`, so an empty fleet means either the\n"
            "package failed to import or every agent lost its `AGENT = ...` line.\n"
        )

    lines = [
        f"{'AGENT':<22} {'STATE':<5} {'LAST RUN':>9} {'CADENCE':>8} "
        f"{'STATUS':<8} {'IN':>6} {'OUT':>6} {'24H':>5} {'FAIL':>5}",
        "-" * 92,
    ]
    for health in fleet:
        lines.append(
            f"{health.agent:<22} "
            f"{_STATE_MARK[health.state]:<5} "
            f"{format_age(health.age):>9} "
            f"{format_age(health.cadence):>8} "
            f"{(health.last_status or '-'):<8} "
            f"{health.items_in:>6} "
            f"{health.items_out:>6} "
            f"{health.runs_24h:>5} "
            f"{health.failures_24h:>5}"
        )

    notes: list[str] = []
    for health in fleet:
        if health.is_stuck:
            notes.append(
                f"{health.agent}: STUCK — a row has been at `running` for "
                f"{format_age(health.age)}, past the {format_age(STALE_RUN)} stale "
                "window. Nothing will finish it or retry it. This is what a "
                "container restart mid-run leaves behind; the overlap guard has "
                "already stopped honouring it, so later runs went ahead while "
                "this row stayed open."
            )
        elif health.state == "late" and health.overdue_by is not None:
            notes.append(
                f"{health.agent}: LATE by {format_age(health.overdue_by)} beyond "
                f"the {MISSED_CYCLES_BEFORE_LATE:g} cycles it is allowed. Last run "
                f"{health.last_status}. Check the worker and beat containers — a "
                "beat that is not running produces exactly this, with no errors "
                "anywhere, because the agent is not failing, it is not being asked."
            )
        elif health.state == "never_run":
            notes.append(
                f"{health.agent}: has never run. Expected on a fresh database; "
                "otherwise the agent was added and beat was never restarted."
            )
        elif health.state == "unknown":
            notes.append(
                f"{health.agent}: cadence `{health.cron}` is a shape "
                "`cadence_of()` does not parse, so lateness cannot be judged. "
                f"Last run {format_age(health.age)} ago, status "
                f"{health.last_status}. Teach `cadence_of` the shape or read this "
                "one by eye."
            )
        for problem in health.errors[:3]:
            notes.append(f"{health.agent}: last run reported — {problem}")

    if notes:
        lines.append("")
        lines.extend(notes)
    return "\n".join(lines) + "\n"


def worst_state(fleet: list[AgentHealth]) -> HealthState:
    """
    The fleet's single worst state, for the CLI's exit code.

    `never_run` and `unknown` are **not** counted as worse than `working`: the
    first is the normal state of a fresh database and the second is this module
    declining to guess, and neither should make a health check in a shell script
    report a failure. `late` and `problem` should.
    """
    # Annotated so the literals narrow to `HealthState` rather than `str`, which
    # is what lets this return without a cast.
    ranked: tuple[HealthState, ...] = ("problem", "late")
    for state in ranked:
        if any(health.state == state for health in fleet):
            return state
    return "working"
