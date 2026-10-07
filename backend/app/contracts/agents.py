"""
Agent contracts — IMPLEMENTATION_PLAN.md §6.3.

Eight agents are planned and none of them may build their own dependencies: an
agent receives an `AgentContext` and returns an `AgentResult`, and that is the
whole of its relationship with the rest of the system. The payoff is that a run
is reproducible (pass a different `now`), testable (pass `dry_run=True`) and
observable (`AgentResult` is exactly what goes into the `agent_runs` table).

No agent exists yet. The first is the Geolocation Agent in D03.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: UUID
    now: datetime
    dry_run: bool = False


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
