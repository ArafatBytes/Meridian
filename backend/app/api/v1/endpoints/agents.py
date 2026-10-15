"""
Agent fleet status, as a signed-in user is shown it. B9.

    GET /api/v1/agents/status   one card per agent: working, late, or a problem

## Why this needs a token when `/ingestion/status` does not

`/ingestion/status` is deliberately unauthenticated, and its docstring gives the
reason: *"it describes public news, not a user."* That reason does not carry over.
This endpoint describes **our deployment** — which parts of the system are
currently not working, and for how long. In a safety app that is operational
posture, and the audience for "the alert dispatcher has been down for six hours"
is not a member of the public. It costs nothing to gate: the screen that renders
it lives behind Profile, where the caller is signed in already.

## Why the payload is narrower than what the CLI prints

`app/agents/health.py` returns error text, item counts, failure tallies and a
stuck-run distinction. None of that is here — `AgentHealthReport`'s docstring
gives the reason for each omission. The same function feeds both readers, so the
operator's view and the user's view can never disagree about whether an agent is
healthy; they differ only in how much they say about it.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.health import fleet_health
from app.contracts.agents import AgentHealthReport, FleetStatus
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter()


def _replaying() -> bool:
    """Same test as `endpoints/ingestion.py`, for the same reason."""
    return settings.RISK_SURFACE_IMPL.strip().lower() == "seeded"


@router.get("/status", response_model=FleetStatus)
async def agents_status(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> FleetStatus:
    now = datetime.now(UTC)
    if _replaying():
        # Offline replay: there are no schedules and no `agent_runs` to read, so
        # an empty list with `mode="replay"` is the truthful answer. Reporting
        # five agents as `never_run` would be technically accurate and read as
        # five things being broken.
        return FleetStatus(mode="replay", checked_at=now, agents=[])

    return FleetStatus(
        mode="live",
        checked_at=now,
        agents=[
            AgentHealthReport(
                agent=health.agent,
                state=health.state,
                last_run_at=health.last_started_at,
                seconds_since_last_run=(
                    int(health.age.total_seconds()) if health.age is not None else None
                ),
                cadence_seconds=(
                    int(health.cadence.total_seconds()) if health.cadence is not None else None
                ),
                runs_last_24h=health.runs_24h,
            )
            for health in await fleet_health(db, now=now)
        ],
    )
