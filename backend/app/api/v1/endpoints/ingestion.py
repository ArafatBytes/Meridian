"""
Live news ingestion, as the map sees it. DEMO_PLAN.md D04.

    GET  /api/v1/ingestion/status   the last Live Risk Agent run — the "updated 4 min ago"
    POST /api/v1/ingestion/run      start a run now (signed-in users), returns 202

The schedule runs the agent every 15 minutes on its own (`docker compose` worker).
`run` exists for the stage: waiting up to a quarter of an hour for beat 1 is not a
plan. It runs in this process as a background task — the API is the one service
guaranteed to be up when someone taps the button — and the registry's overlap guard
makes a tap during a scheduled run a no-op rather than a second run.

With `RISK_SURFACE_IMPL=seeded` there is no database to report on and nothing to
ingest into: the map is showing the captured replay. `status` says so instead of
failing, and `run` answers 409, so the app can label the offline mode honestly.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.live_risk import AGENT as LIVE_RISK
from app.agents.registry import run_agent
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter()


class RunSummary(BaseModel):
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "ok", "partial", "failed"]
    documents_read: int
    flags_published: int
    error_count: int


class IngestionStatus(BaseModel):
    """`mode` is `live` (database, agent on a schedule) or `replay` (offline, seeded)."""

    mode: Literal["live", "replay"]
    last_run: RunSummary | None


def _replaying() -> bool:
    return settings.RISK_SURFACE_IMPL.strip().lower() == "seeded"


@router.get("/status", response_model=IngestionStatus)
async def ingestion_status(db: AsyncSession = Depends(get_db)) -> IngestionStatus:
    """Unauthenticated, like `/risk/flags`: it describes public news, not a user."""
    if _replaying():
        return IngestionStatus(mode="replay", last_run=None)
    row = (
        await db.execute(
            text(
                "select started_at, finished_at, status, items_in, items_out, "
                "jsonb_array_length(errors) as error_count "
                "from public.agent_runs where agent = :agent and dry_run = false "
                "order by started_at desc limit 1"
            ),
            {"agent": LIVE_RISK.name},
        )
    ).first()
    if row is None:
        return IngestionStatus(mode="live", last_run=None)
    return IngestionStatus(
        mode="live",
        last_run=RunSummary(
            started_at=row.started_at,
            finished_at=row.finished_at,
            status=row.status,
            documents_read=row.items_in,
            flags_published=row.items_out,
            error_count=row.error_count,
        ),
    )


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def ingestion_run(
    background: BackgroundTasks,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    if _replaying():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Offline replay mode (RISK_SURFACE_IMPL=seeded): there is nothing to fetch into.",
        )
    background.add_task(run_agent, LIVE_RISK.name)
    return {"status": "accepted"}
