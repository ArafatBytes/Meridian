"""
Expiry sweep — retire flags, clusters and news crime past `expires_at`. D02's
housekeeping, scheduled in D04, extended to `community_clusters` in B13 and to
`news_crime_incidents` in S30.

The same statement as `scripts/sweep_expired_flags.py`, which stays as the manual
path. **The sweep does not decide what is live** — every surface stops serving a
row the moment it passes `expires_at`, whether or not this has ever run. It only
keeps the tables from accumulating live-status rows that are not live, and it keeps
them (`status = 'expired'`) rather than deleting them, because an expired row is the
evidence that the surface retires things on its own.

Three tables, one agent. They are swept together because they are one piece of
housekeeping with one schedule and one failure mode; a second agent would mean a
second `agent_runs` row saying the same thing. The predicates differ only in which
statuses count as live, which is the one thing each table disagrees about.

`news_crime_incidents` matters most of the three for this sweep, because it is the
surface whose rows would be worst to leave standing. A decayed mobility flag is a
stale traffic claim; a news crime incident that never retires is a permanent
accusation attached to a street corner. Its five-day half-life means it falls below
the serve threshold about eighteen days after the report, and this is what moves it
out of `published` once it does.

`community_clusters` is swept *as well as* being reconciled by
`report_corroboration`, and the two are not redundant. The corroboration agent
retires a cluster whose **evidence** is gone (withdrawn, removed, aged out of the
window); this retires one whose **severity** has decayed below the serve threshold
while its reports are all still there. A cluster can hit the second long before the
first: decay runs out around ten days past its newest report, and the candidate
window is a fortnight.

Evaluated at `ctx.now`, not the database's `now()`, so a replayed run retires what
was due at that instant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from sqlalchemy import text

from app.contracts.agents import AgentContext, AgentResult, BaseAgent

_FLAGS_DUE: Final = "status in ('unconfirmed', 'confirmed') and expires_at <= :now"
_CLUSTERS_DUE: Final = "status in ('provisional', 'corroborated') and expires_at <= :now"
# One live status rather than two: corroboration on this surface is derived on read
# from `source_count`, not stored as a status. See `app/scoring/news_crime.py`.
_NEWS_CRIME_DUE: Final = "status = 'published' and expires_at <= :now"

_TABLES: Final[tuple[tuple[str, str], ...]] = (
    ("public.risk_flags", _FLAGS_DUE),
    ("public.community_clusters", _CLUSTERS_DUE),
    ("public.news_crime_incidents", _NEWS_CRIME_DUE),
)


class ExpirySweepAgent(BaseAgent):
    name = "expiry_sweep"
    cron = "*/30 * * * *"

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("expiry_sweep needs ctx.db; the runner provides it")

        swept: dict[str, int] = {}
        for table, predicate in _TABLES:
            if ctx.dry_run:
                count = (
                    await ctx.db.execute(
                        text(f"select count(*) from {table} where {predicate}"),
                        {"now": ctx.now},
                    )
                ).scalar_one()
            else:
                result = await ctx.db.execute(
                    text(f"update {table} set status = 'expired' where {predicate}"),
                    {"now": ctx.now},
                )
                count = getattr(result, "rowcount", 0)
            swept[table] = int(count)

        if not ctx.dry_run:
            await ctx.db.commit()

        total = sum(swept.values())
        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status="ok",
            items_in=total,
            items_out=total,
            metrics={
                "flags_expired": float(swept["public.risk_flags"]),
                "clusters_expired": float(swept["public.community_clusters"]),
                "news_crime_expired": float(swept["public.news_crime_incidents"]),
            },
        )


AGENT = ExpirySweepAgent()
