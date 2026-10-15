"""
Agent contracts — IMPLEMENTATION_PLAN.md §6.3.

Eight agents are planned and none of them may build their own dependencies: an
agent receives an `AgentContext` and returns an `AgentResult`, and that is the
whole of its relationship with the rest of the system. The payoff is that a run
is reproducible (pass a different `now`), testable (pass `dry_run=True`) and
observable (`AgentResult` is exactly what goes into the `agent_runs` table).

The Geolocation Agent (D03, `app/geo/agent.py`) is a function, not a scheduled
agent. The first `BaseAgent` is the Live Risk Agent in D04.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

AgentStatus = Literal["ok", "partial", "failed"]
"""
`partial` is deliberate and is the common case: three news sources, one is down,
the run still produced flags. Collapsing that into `failed` would mean the fleet
looks broken whenever any publisher has a bad day.
"""


class AgentResult(BaseModel):
    """One run of one agent. Persisted to `agent_runs`."""

    agent: str
    run_id: UUID
    started_at: datetime
    finished_at: datetime
    status: AgentStatus
    items_in: int = Field(ge=0)
    items_out: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class AgentContext(BaseModel):
    """
    Everything an agent may touch. Injected — agents never build their own.

    `now` is passed in rather than read, so a run can be replayed against a past
    instant. `dry_run` must reach every write path in the agent; an agent that
    ignores it is a bug, not a style choice.

    `db` arrived in D04 with the first agent that writes (CONTRACT CHANGE, logged in
    PROGRESS.md). The runner opens the session and owns its lifetime; an agent
    that needs the database and gets `None` must fail its run rather than open its
    own connection, because a connection the runner did not open is one it cannot
    close when the run is cancelled.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: UUID
    now: datetime
    dry_run: bool = False
    db: AsyncSession | None = None


class BaseAgent(ABC):
    """
    Base for every agent.

    Each agent module exports `AGENT = MyAgent()`, and `agents/registry.py`
    (D04) discovers them and registers `cron` with Celery beat. Adding an agent
    is therefore one new directory and never an edit to a central list.
    """

    name: ClassVar[str]
    cron: ClassVar[str | None] = None  # the registry reads this
    enabled_by_default: ClassVar[bool] = True

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentResult: ...


# ============================================================================
# B9 — fleet status, as a signed-in user is shown it
# ============================================================================

AgentHealthState = Literal["working", "late", "problem", "never_run", "unknown"]
"""
Mirrors `app/agents/health.py :: HealthState`. Declared again here rather than
imported because this is the **wire** vocabulary: the client has a matching union
and `tests/invariants/test_contracts_do_not_drift.py` compares the two, so this
is the definition that is contractually frozen. `health.py` is free to add an
internal distinction (it separates a stuck run from a failed one) without that
becoming a new value a client must learn.
"""


class AgentHealthReport(BaseModel):
    """
    One agent's health, narrowed to what a user may see.

    **What is deliberately not here, and why.** `errors` is a Python exception
    repr — noise to a user and a small amount of help to anybody probing the
    deployment. `items_in`/`items_out` do not mean the same thing across agents,
    so one column of them invites a comparison that is not valid. `failures_24h`
    reads as alarming without being actionable: a user cannot retry an agent.
    All four stay in `python -m app.agents status`, where the reader can act.

    What is here is a state, a measured age and the cadence it is measured
    against — enough for a user to answer "is what I am looking at current", and
    not enough to mislead them about anything else.
    """

    agent: str
    state: AgentHealthState
    last_run_at: datetime | None
    seconds_since_last_run: int | None
    cadence_seconds: int | None
    runs_last_24h: int


class FleetStatus(BaseModel):
    """
    `mode` is `live` (agents on schedules, reading the database) or `replay`
    (`RISK_SURFACE_IMPL=seeded`, offline, nothing scheduled and nothing to
    report). Same two values and the same reason as `IngestionStatus`: the demo
    runs offline, and a status screen that errored in replay mode would be a
    broken screen on stage rather than an honest one.

    `checked_at` is the server's instant, and the client ages everything from it
    rather than from the handset clock — a phone whose clock is twenty minutes
    out would otherwise render "updated 20 minutes ago" for a run that just
    finished, or worse, a negative age.
    """

    mode: Literal["live", "replay"]
    checked_at: datetime
    agents: list[AgentHealthReport]
