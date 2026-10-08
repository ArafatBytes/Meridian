"""
Finding agents, scheduling them, and recording every run. IMPLEMENTATION_PLAN.md §6.3.

    agents()                 {name: agent} for every app/agents/*.py exporting AGENT
    beat_schedule()          the Celery beat table, built from each agent's `cron`
    await run_agent(name)    one run: the session, the agent_runs row, the result

`run_agent` is the only way an agent runs — from Celery beat, from the API's "fetch
news now" button, and from `python -m app.agents run`. So the `agent_runs` row, the
overlap guard and session ownership live here once, not in each agent.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any, Final
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.agents as package
from app.contracts.agents import AgentContext, AgentResult, BaseAgent
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

STALE_RUN: Final = timedelta(minutes=20)
"""
A `running` row younger than this means the agent is mid-run, and a second run is
skipped rather than started. Older than this, the earlier run is assumed dead (a
container restart mid-run leaves its row at `running` forever), so it no longer
blocks — that stuck row is exactly what Track B's fleet view should surface.
"""

_NOT_AGENTS: Final = frozenset({"registry", "__main__"})


@cache
def agents() -> dict[str, BaseAgent]:
    found: dict[str, BaseAgent] = {}
    for module in pkgutil.iter_modules(package.__path__):
        if module.name in _NOT_AGENTS:
            continue
        agent = getattr(importlib.import_module(f"app.agents.{module.name}"), "AGENT", None)
        if isinstance(agent, BaseAgent):
            found[agent.name] = agent
    return found


def beat_schedule() -> dict[str, dict[str, Any]]:
    """Celery beat entries for every agent that declares a cron and is on by default."""
    from celery.schedules import crontab

    schedule: dict[str, dict[str, Any]] = {}
    for name, agent in agents().items():
        if agent.cron and agent.enabled_by_default:
            minute, hour, day_of_month, month_of_year, day_of_week = agent.cron.split()
            schedule[name] = {
                "task": "agents.run",
                "schedule": crontab(
                    minute=minute,
                    hour=hour,
                    day_of_month=day_of_month,
                    month_of_year=month_of_year,
                    day_of_week=day_of_week,
                ),
                "args": (name,),
            }
    return schedule


async def _running_since(db: AsyncSession, name: str, now: datetime) -> datetime | None:
    row = (
        await db.execute(
            text(
                "select started_at from public.agent_runs where agent = :agent "
                "and status = 'running' and started_at > :after "
                "order by started_at desc limit 1"
            ),
            {"agent": name, "after": now - STALE_RUN},
        )
    ).first()
    return row.started_at if row else None


async def run_agent(name: str, *, dry_run: bool = False) -> AgentResult | None:
    """
    Run one agent once. Returns its result, or None if a run was already in progress.

    `dry_run` reaches the agent and also skips the `agent_runs` row, so a dry run
    writes nothing at all.
    """
    agent = agents()[name]
    now = datetime.now(UTC)
    run_id = uuid4()

    async with AsyncSessionLocal() as db:
        if not dry_run:
            if (since := await _running_since(db, name, now)) is not None:
                logger.info("%s already running since %s; skipping this run", name, since)
                return None
            await db.execute(
                text(
                    "insert into public.agent_runs (run_id, agent, started_at, status, dry_run) "
                    "values (:run_id, :agent, :started_at, 'running', false)"
                ),
                {"run_id": run_id, "agent": name, "started_at": now},
            )
            await db.commit()

        try:
            result = await agent.run(AgentContext(run_id=run_id, now=now, dry_run=dry_run, db=db))
        except Exception as problem:  # noqa: BLE001 - recorded as a failed run, not lost
            logger.exception("%s failed", name)
            await db.rollback()
            result = AgentResult(
                agent=name,
                run_id=run_id,
                started_at=now,
                finished_at=datetime.now(UTC),
                status="failed",
                items_in=0,
                items_out=0,
                errors=[f"{type(problem).__name__}: {problem}"],
            )

        if not dry_run:
            await db.execute(
                text(
                    "update public.agent_runs set finished_at = :finished_at, status = :status, "
                    "items_in = :items_in, items_out = :items_out, "
                    "errors = cast(:errors as jsonb), metrics = cast(:metrics as jsonb) "
                    "where run_id = :run_id"
                ),
                {
                    "run_id": run_id,
                    "finished_at": result.finished_at,
                    "status": result.status,
                    "items_in": result.items_in,
                    "items_out": result.items_out,
                    "errors": json.dumps(result.errors[:50], ensure_ascii=False),
                    "metrics": json.dumps(result.metrics),
                },
            )
            await db.commit()

    logger.info(
        "%s %s: %d in, %d out, %d error(s)",
        name,
        result.status,
        result.items_in,
        result.items_out,
        len(result.errors),
    )
    return result
