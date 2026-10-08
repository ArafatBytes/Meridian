"""
Celery — the schedule that runs agents. D04, source sprint S04.

    celery -A app.core.celery_app worker -B --concurrency 1     (docker compose: worker)

The beat schedule is built from `app.agents.registry`: every agent module exporting
`AGENT` with a `cron` gets an entry, so scheduling a new agent is never an edit here.

Until D04 this file scheduled `crime_service.update_crime_scores` and
`storage_service.cleanup_old_videos` — two modules that never existed, with no task
definitions anywhere, so beat crashed on boot and the worker was left out of
docker-compose. Both entries are deleted, not stubbed.

One task, `agents.run`, for every agent. It runs the agent's async code in a fresh
event loop per invocation, and disposes the engine afterwards: asyncpg connections
belong to the loop that opened them, so a pooled connection carried into the next
task's loop fails with "attached to a different loop".
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "Meridian",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Dhaka",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
)


async def _run(name: str) -> dict[str, Any] | None:
    from app.agents.registry import run_agent
    from app.core.database import engine

    try:
        result = await run_agent(name)
        return result.model_dump(mode="json") if result else None
    finally:
        await engine.dispose()


@celery_app.task(name="agents.run")
def run_agent_task(name: str) -> dict[str, Any] | None:
    return asyncio.run(_run(name))


def _schedule() -> dict[str, dict[str, Any]]:
    from app.agents.registry import beat_schedule

    return beat_schedule()


celery_app.conf.beat_schedule = _schedule()
