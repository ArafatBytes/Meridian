"""
Expiry sweep — retire flags past `expires_at`. D02's housekeeping, scheduled in D04.

The same statement as `scripts/sweep_expired_flags.py`, which stays as the manual
path. **The sweep does not decide what is live** — both surfaces stop serving a flag
the moment it passes `expires_at`, whether or not this has ever run. It only keeps
the table from accumulating live-status rows that are not live, and it keeps them
(`status = 'expired'`) rather than deleting them, because an expired flag is the
evidence that the surface retires things on its own.

Evaluated at `ctx.now`, not the database's `now()`, so a replayed run retires what
was due at that instant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from sqlalchemy import text

from app.contracts.agents import AgentContext, AgentResult, BaseAgent

_DUE: Final = "status in ('unconfirmed', 'confirmed') and expires_at <= :now"


class ExpirySweepAgent(BaseAgent):
    name = "expiry_sweep"
    cron = "*/30 * * * *"

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("expiry_sweep needs ctx.db; the runner provides it")
        if ctx.dry_run:
            due = (
                await ctx.db.execute(
                    text(f"select count(*) from public.risk_flags where {_DUE}"), {"now": ctx.now}
                )
            ).scalar_one()
        else:
            result = await ctx.db.execute(
                text(f"update public.risk_flags set status = 'expired' where {_DUE}"),
                {"now": ctx.now},
            )
            due = getattr(result, "rowcount", 0)
            await ctx.db.commit()
        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status="ok",
            items_in=int(due),
            items_out=int(due),
        )


AGENT = ExpirySweepAgent()
