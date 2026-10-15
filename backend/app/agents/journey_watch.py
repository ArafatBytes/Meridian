"""
The thing that notices. JG2.

Every minute, two questions and no third:

    1. which active journeys are past their deadline and have not been asked?
       -> push the check-in, move `normal` -> `check_in_sent`

    2. which asked journeys have gone unanswered past the window?
       -> write `unanswered_at`, and **do nothing else**

Branch 2 sends nothing, tells nobody and changes no state. It exists to produce
the record that the escalation chain is not allowed to act without -- "every step
past the first requires a recorded non-response with a timestamp"
(JOURNEY_GUARDIAN.md §7). JG3 is what reads it.

That is worth being explicit about, because an agent whose second branch
currently does nothing visible is exactly the kind of code a later reader
deletes as dead. It is not dead; it is the half of the mechanism that makes the
other half safe to build.

## Why a sweep and not a scheduled job per journey

The obvious alternative is to schedule a task at the deadline when the journey
starts -- one timer per trip, firing exactly on time, no polling.

It was rejected because a deadline *moves*. Every heartbeat slides it and every
answer extends it, so a per-journey timer would have to be cancelled and
rescheduled on each one, which is a distributed-state problem (a timer that
outlives a rescheduling fires early; one that gets lost never fires) in exchange
for up to 60 seconds of latency. A sweep has no state between runs: it reads the
deadline that is in the row right now, which is by construction the current one.

Sixty seconds of latency is affordable here in a way it is not for
`alert_dispatch`, whose own note explains that its minute cadence *is* its
latency budget. A check-in that arrives up to a minute late is a check-in that
arrives; the grace period in front of it is ten minutes.

## Why it is cheap

Both queries are indexed single-table reads against `idx_journeys_due`, which is
partial on `state = 'active'` -- and the overwhelming majority of rows in this
table at any time are finished journeys. The common run reads nothing, sends
nothing and writes one `agent_runs` row. Work scales with journeys in progress,
which is the number this feature is about.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import text

from app.alerts.expo import HttpPushTransport, PushTransport, default_transport
from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.journeys.checkin import compose_check_in
from app.journeys.deadline import CHECK_IN_WINDOW

logger = logging.getLogger(__name__)


_DUE_FOR_CHECK_IN: Final = text(
    """
    select journey_id, user_id
      from public.journeys
     where state = 'active'
       and escalation_state = 'normal'
       and deadline_at <= :now
     order by deadline_at
     -- A bound rather than no limit. If something has gone wrong and ten
     -- thousand journeys are due at once, sending ten thousand pushes inside one
     -- minute-long run is the worst available response: it would exhaust the
     -- Expo quota, delay the next sweep past its own window, and buzz every
     -- phone in the city. Taking the oldest few hundred and leaving the rest for
     -- the next run degrades instead of collapsing.
     limit 500
    """
)


_MARK_SENT: Final = text(
    """
    update public.journeys
       set escalation_state = 'check_in_sent',
           check_in_sent_at = :now,
           -- The previous ask's record, cleared because this is a new question.
           -- `unanswered_at` means "the ask that is outstanding went unanswered",
           -- not "this journey has ever been unanswered".
           unanswered_at = null
     where journey_id = :journey_id
       and state = 'active'
       -- Re-checked here, not just in the SELECT above. Between the two the user
       -- may have arrived, cancelled, or answered a check-in from a run that
       -- overlapped this one. Without it a journey that ended four seconds ago
       -- would be marked as having an outstanding question.
       and escalation_state = 'normal'
    """
)


_RECORD_NON_RESPONSE: Final = text(
    """
    update public.journeys
       set unanswered_at = :now
     where state = 'active'
       and escalation_state = 'check_in_sent'
       and unanswered_at is null
       and check_in_sent_at <= :cutoff
       -- An answer to a *previous* question does not count. A journey asked at
       -- 10:40, answered at 10:41 and asked again at 10:56 has a real
       -- `answered_at` that is about the earlier question, and reading it alone
       -- would make the second question look answered the moment it was asked.
       and (answered_at is null or answered_at < check_in_sent_at)
    returning journey_id
    """
)


_DEVICES: Final = text(
    """
    select expo_push_token
      from public.push_devices
     where user_id = :user_id and disabled_at is null
    """
)


class JourneyWatchAgent(BaseAgent):
    name = "journey_watch"
    cron = "* * * * *"
    """
    Every minute. The sweep interval is the worst-case lateness of a check-in,
    and a deadline is only meaningful to the minute anyway -- the grace period in
    front of it is ten.

    It is also what makes `MIN_DEADLINE` of two minutes a usable walkthrough: a
    deadline set for a shorter interval than the sweep would be a deadline whose
    check-in arrives at an unpredictable moment, which is not something a
    walkthrough step can assert on.
    """

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("journey_watch needs ctx.db; the runner provides it")

        errors: list[str] = []
        metrics: dict[str, float] = dict.fromkeys(
            ("due", "sent", "failed", "no_device", "unanswered"), 0.0
        )

        # Reaches the transport, not only the writes. A dry run that buzzed a real
        # phone would be useless for the rehearsal it exists for.
        transport = default_transport(dry_run=ctx.dry_run)
        try:
            due = (await ctx.db.execute(_DUE_FOR_CHECK_IN, {"now": ctx.now})).all()
            metrics["due"] = float(len(due))

            for row in due:
                sent = await self._ask(
                    ctx, transport=transport, journey_id=row.journey_id, user_id=row.user_id
                )
                if sent is None:
                    metrics["no_device"] += 1.0
                elif sent:
                    metrics["sent"] += 1.0
                else:
                    metrics["failed"] += 1.0

            # Branch 2. Deliberately after the sends and in the same transaction:
            # a journey asked in *this* run cannot also be recorded as unanswered
            # by it, because `check_in_sent_at` is `ctx.now` and the cutoff is
            # `ctx.now - CHECK_IN_WINDOW`.
            unanswered = (
                await ctx.db.execute(
                    _RECORD_NON_RESPONSE,
                    {"now": ctx.now, "cutoff": ctx.now - CHECK_IN_WINDOW},
                )
            ).all()
            metrics["unanswered"] = float(len(unanswered))
            for row in unanswered:
                # Logged at warning because in JG3 this is the line that precedes
                # somebody's guardian being told. Until then it is the only place
                # a non-response is visible without a database query.
                logger.warning("journey %s did not answer its check-in", row.journey_id)

            if ctx.dry_run:
                await ctx.db.rollback()
            else:
                await ctx.db.commit()

        except Exception as problem:  # noqa: BLE001 - a failed sweep must not kill the beat
            await ctx.db.rollback()
            logger.exception("journey watch sweep failed")
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

        # `partial` when a push was rejected: the sweep did its job and a dead
        # token or an Expo outage is not its failure. Same reading as
        # `alert_dispatch`. `failed` is reserved for the sweep not completing.
        status: AgentStatus = "partial" if metrics["failed"] else "ok"

        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status=status,
            items_in=int(metrics["due"]),
            items_out=int(metrics["sent"]),
            errors=errors,
            metrics=metrics,
        )

    async def _ask(
        self,
        ctx: AgentContext,
        *,
        transport: PushTransport,
        journey_id: object,
        user_id: object,
    ) -> bool | None:
        """
        Push one check-in and mark the journey as asked.

        `None` when the person has no registered device.

        **The state is moved whether or not the push lands**, and that ordering is
        deliberate. A journey left at `normal` because Expo was down would be
        swept again the next minute and the one after, buzzing the phone once a
        minute for the rest of the trip the moment delivery recovered. Worse, the
        clock would never start on the non-response, so a phone that is genuinely
        gone would never produce the record JG3 escalates on -- the failure mode
        would be silence, which is the one outcome this feature exists to prevent.

        A check-in that was sent and not delivered still deserves an answer, and
        the person has the journey card in the app either way.
        """
        assert ctx.db is not None  # guarded by the caller

        tokens = (await ctx.db.execute(_DEVICES, {"user_id": user_id})).scalars().all()

        await ctx.db.execute(_MARK_SENT, {"journey_id": journey_id, "now": ctx.now})

        if not tokens:
            # Not an error. Plenty of accounts have never granted notification
            # permission, and the journey card in the app is the other half of
            # this feature for exactly that reason.
            logger.info("journey %s is due a check-in but has no device", journey_id)
            return None

        message = compose_check_in(journey_id=str(journey_id))
        receipts = await transport.send([(token, message) for token in tokens])
        return any(receipt.ok for receipt in receipts)


AGENT = JourneyWatchAgent()
