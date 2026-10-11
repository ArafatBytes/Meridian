"""
Alert Dispatch Agent — the flag on the map becomes a buzz in a pocket. B6a / S16.

    push_devices (active, located, fresh)
        ─▶ RiskSurface.flags_near  ─▶ policy.decide  ─▶ compose_alert
             ─▶ sent_alerts (claim)  ─▶ PushTransport  ─▶ sent_alerts (settle)

Phase 3's exit criteria ask that *"a real device receives a push within 60 s of a
flag appearing on its corridor"*, which is what sets the cadence below. Everything
else about this agent is thin on purpose: it owns the schedule, the transport's
lifetime and the `AgentResult`, and delegates every decision to `app/alerts/`.

## Why an agent rather than a hook on flag publication

The tempting design is to call the dispatcher from `live_risk._publish`, straight
after a flag is written. It is immediate and it needs no schedule. It was rejected
for three reasons, in increasing order of how much they would have hurt:

1. **Flags arrive from four places** — `live_risk`, `scheduled_risk`, the fixture
   seeder, and Rumour Guard promoting an existing flag to `confirmed`. A hook
   means four call sites and four chances for one to be forgotten; the one that
   would have been forgotten is the promotion, which is the single most
   alert-worthy event in the system.
2. **Publication is not the only thing that makes a flag newly relevant.** A user
   who moves is the other half, and there is no publish event for that at all. A
   sweep covers both with one mechanism.
3. **An agent is observable.** `agent_runs` gets a row per run with the refusal
   breakdown in `metrics`, the overlap guard stops two sweeps colliding, and the
   fleet view (B9) sees it beside the other seven. A hook inside another agent's
   write path is invisible until it misbehaves, and its failures get attributed to
   whichever agent happened to be publishing.

The cost is latency: up to one minute between a flag being written and the push.
That is inside the Phase 3 budget, and it buys the three properties above.

## Scope: this cannot yet warn someone who is walking

The dispatcher knows where a device was when the app was last in the foreground,
because that is all `push_devices.last_location` holds — background location and
true geofence crossing are **S17**, the other half of B6a, and they are not
built. So the honest description of what this agent does is *"tells you about
something near where you last were"*, not *"warns you as you approach"*.

`DEVICE_LOCATION_MAX_AGE` is what keeps that from becoming a lie, by refusing to
alert on a position older than six hours. `docs/walkthroughs/B6a.md` states the
limit in the same words, and so does the preferences screen: the user is the one
who most needs to know which of the two promises this is.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final

from app.alerts.expo import HttpPushTransport, default_transport
from app.alerts.policy import Refusal
from app.alerts.service import dispatch_for_devices
from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.scoring.factory import get_risk_surface

logger = logging.getLogger(__name__)

_REFUSAL_KEYS: Final[tuple[str, ...]] = tuple(refusal.value for refusal in Refusal)
"""
Every refusal reason, so each one appears in `metrics` even at zero.

A metrics dict whose keys come and goes with the data is unreadable over time: a
missing `rate_capped` could mean nobody was capped or could mean the key was
never emitted, and a chart of the two looks identical. Pre-seeding to 0.0 is the
same thing `scheduled_risk` does with `dict.fromkeys`.
"""


class AlertDispatchAgent(BaseAgent):
    name = "alert_dispatch"
    cron = "* * * * *"
    """
    Every minute.

    Phase 3's exit criterion is a push within 60 s of a flag appearing on a
    corridor, and a sweep is the only thing that notices, so the sweep interval
    *is* the latency budget. There is no slack to spend: two minutes would make
    the criterion unmeetable by construction.

    A minute-cadence agent is affordable here because the sweep is three bulk
    queries plus one spatial query per active device, and it sends nothing when
    the city is quiet — the common case is a run that reads a handful of rows,
    refuses everything on `already_sent`, and stops. It writes an `agent_runs`
    row each time, which is ~1,440 a day; that is the main cost, and the fleet
    view (B9) is what will eventually want them trimmed.
    """

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("alert_dispatch needs ctx.db; the runner provides it")

        errors: list[str] = []
        metrics: dict[str, float] = dict.fromkeys(
            ("devices", "candidates", "sent", "failed", *_REFUSAL_KEYS), 0.0
        )

        # `dry_run` reaches the transport, not just the writes. A dry run that
        # buzzed a real phone would be useless for the rehearsal it exists for —
        # see `NullPushTransport`.
        transport = default_transport(dry_run=ctx.dry_run)
        try:
            outcome = await dispatch_for_devices(
                ctx.db,
                surface=get_risk_surface(ctx.db),
                transport=transport,
                now=ctx.now,
            )
        except Exception as problem:  # noqa: BLE001 - a failed sweep must not kill the beat
            await ctx.db.rollback()
            logger.exception("alert dispatch sweep failed")
            errors.append(f"{type(problem).__name__}: {problem}")
            return AgentResult(
                agent=self.name,
                run_id=ctx.run_id,
                started_at=ctx.now,
                finished_at=datetime.now(UTC),
                status="failed",
                items_in=0,
                items_out=0,
                errors=errors,
                metrics=metrics,
            )
        finally:
            if isinstance(transport, HttpPushTransport):
                await transport.aclose()

        metrics["devices"] = float(outcome.devices)
        metrics["candidates"] = float(outcome.candidates)
        metrics["sent"] = float(outcome.sent)
        metrics["failed"] = float(outcome.failed)
        for reason, count in outcome.refusals.items():
            metrics[reason] = float(count)

        # `partial`, not `failed`, when a push was rejected: the sweep itself did
        # its job, and a dead token or an Expo outage is a publisher-side problem.
        # That is the same reading `AgentStatus` documents for a news source being
        # down -- "three news sources, one is down, the run still produced flags".
        #
        # `failed` is reserved for the sweep not completing at all, which is the
        # early return above.
        status: AgentStatus = "partial" if outcome.failed else "ok"

        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status=status,
            # `items_in` is devices considered, `items_out` is pushes sent. A run
            # reading `in=12 out=0` with `already_sent=37` is a healthy quiet
            # minute; `in=0` means nobody has the app open, which is a different
            # problem and worth being able to tell apart at a glance.
            items_in=outcome.devices,
            items_out=outcome.sent,
            errors=errors,
            metrics=metrics,
        )


AGENT = AlertDispatchAgent()
