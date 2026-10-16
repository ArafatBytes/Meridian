"""
The thing that notices. JG2, extended by JG3.

Every minute:

    1. which active journeys are past their deadline and have not been asked?
       -> push the check-in, move `normal` -> `check_in_sent`

    2. which asked journeys have gone unanswered past the window?
       -> write `unanswered_at`, and **do nothing else**

    3. which journeys have a guardian who has not been told they started?
       -> email the guardian, stamp `started_notice_at`

    4. which journeys arrived with a guardian who has not been told?
       -> email the guardian, stamp `arrived_notice_at`

Branch 2 sends nothing, tells nobody and changes no state. It exists to produce
the record that the escalation chain is not allowed to act without -- "every step
past the first requires a recorded non-response with a timestamp"
(JOURNEY_GUARDIAN.md §7), and JG3's escalation branches are what read it.

That is worth being explicit about, because an agent whose second branch
currently does nothing visible is exactly the kind of code a later reader
deletes as dead. It is not dead; it is the half of the mechanism that makes the
other half safe to build.

## Why the notices are sent from here and not from the endpoint

Branches 3 and 4 could have lived in `POST /journeys` and `POST
/journeys/{id}/arrive` -- send the email where the thing happened. They do not,
for three reasons that compound:

* **The response would wait for SMTP.** `send_guardian_message` hands the
  blocking call to a thread so it does not block the event loop, but the request
  cannot return until it finishes. Pressing Start and watching a spinner for
  four seconds while a mail server thinks about it is a worse product than a
  guardian hearing a minute later.
* **A failed send would be lost.** Here the unstamped timestamp *is* the retry
  queue: the next sweep finds the same row and tries again. In a request
  handler, a refused connection is a log line and a guardian who is never told.
* **One sender, not three.** The check-in already goes out from here. Three
  places that send mean three places that need the location rule, the dry-run
  flag and the mark-before-send ordering right.

The cost is up to sixty seconds of delay on "she set off", which is the right
thing to trade for a notice that actually arrives.

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
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import text

from app.alerts.expo import HttpPushTransport, PushTransport, default_transport
from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.journeys.checkin import compose_check_in
from app.journeys.deadline import CHECK_IN_WINDOW
from app.journeys.guardian import (
    GuardianMessage,
    Position,
    arrived_message,
    escalation_message,
    started_message,
)
from app.models.journey import (
    ESCALATION_CHECK_IN_REPEATED,
    ESCALATION_CHECK_IN_SENT,
    ESCALATION_CONTACTS_NOTIFIED,
    ESCALATION_RECORDED_AT,
)
from app.services.email_service import email_service

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
           unanswered_at = null,
           -- And the same for the answer, which JG2 missed.
           --
           -- `journeys_answered_after_asked` says `answered_at >=
           -- check_in_sent_at`. Moving `check_in_sent_at` forward for a second
           -- question while leaving the first question's answer behind it
           -- violates that -- so a journey that was answered once could never
           -- be asked again, and the sweep raised an IntegrityError every
           -- minute for the rest of the trip.
           --
           -- JG2 intended the opposite: `ESCALATION_TRANSITIONS` is a cycle
           -- precisely so "a journey that runs long enough is asked again",
           -- and its own walkthrough has answering at step 10 and being asked
           -- again at step 16. Found by JG3's first dry run against real rows,
           -- because this needs a journey that has actually been answered once
           -- -- which no test fixture had.
           answered_at = null,

           -- And the escalation record, for the same reason squared.
           --
           -- `journeys_repeated_after_asked` says `check_in_repeated_at >=
           -- check_in_sent_at`, and the two after it say the same thing one
           -- rung further up. A journey that escalated, was answered, and is
           -- now being asked again would carry last cycle's
           -- `check_in_repeated_at` *behind* the new `check_in_sent_at` and
           -- violate all three.
           --
           -- **So these five timestamps describe the outstanding question, not
           -- the journey's lifetime.** That is the same choice JG2 made for
           -- `unanswered_at` -- "the ask that is outstanding went unanswered",
           -- not "this journey has ever been unanswered" -- extended to the
           -- whole ladder, and it is what makes the machine a cycle rather
           -- than a one-shot.
           --
           -- The migration's own comment claims the opposite: that an answered
           -- journey "KEEPS these timestamps, because they are the history of
           -- what happened on this trip". That comment is wrong and the file
           -- cannot be edited -- it is applied and checksummed -- so the
           -- correction lives here and in
           -- `test_a_new_question_resets_the_escalation_record`. Keeping a
           -- lifetime history would need the events table JG3 deliberately did
           -- not build.
           check_in_repeated_at = null,
           contacts_notified_at = null,
           full_sos_at = null
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


NOTICE_BACKLOG: Final = timedelta(hours=6)
"""
How far back a notice is still worth sending.

Without a bound, the first sweep after a deployment that had been down would
email guardians about journeys from days ago -- "Rina has started a journey",
about a walk she finished on Tuesday. Worse during a long outage: a backlog of
them at once, which is how a guardian learns to filter Meridian.

Six hours is longer than any plausible restart and shorter than "yesterday". A
journey older than this simply never gets its notice, which is the right
failure: a late "she set off" is misinformation, not information.
"""


_GUARDIAN_FOR = """
    join public.emergency_contacts c on c.id = j.guardian_contact_id
    join auth.users u               on u.id = j.user_id
"""
"""
The two joins every notice needs: who to tell, and whose journey it is.

`auth.users` and not `public.users`. The mirror is a table a teammate dropped
in `20261015160000`, that `Base.metadata.create_all` recreates empty on every
app start, and that `POST /sos` re-populates one row at a time -- so its
contents are whatever those three forces last agreed on. `auth.users` is the
real one and is what `journeys.user_id` references.

The name comes out of `raw_user_meta_data`, where Supabase puts what the person
signed up with. `->>'name'` first because that is the key actually populated in
this project's accounts, `full_name` second because it is the key Supabase
documents, and the email's local part last so a guardian never receives a
message about "null".
"""


_TRAVELLER = """
    coalesce(
        nullif(trim(u.raw_user_meta_data->>'name'), ''),
        nullif(trim(u.raw_user_meta_data->>'full_name'), ''),
        split_part(u.email, '@', 1)
    ) as traveller
"""


_PENDING_STARTED_NOTICE: Final = text(
    f"""
    select j.journey_id, c.email as guardian_email, c.name as guardian_name,
           j.destination_label, j.deadline_at, {_TRAVELLER}
      from public.journeys j
      {_GUARDIAN_FOR}
     where j.state = 'active'
       and j.started_notice_at is null
       and j.started_at >= :backlog_cutoff
       and coalesce(trim(c.email), '') <> ''
     order by j.started_at
     limit 200
    """
)
"""
Journeys whose guardian has not yet been told they began.

`state = 'active'` and not "every journey": a trip that started and ended
inside one sweep interval needs no "she set off" -- branch 4 will send "she
arrived", and sending both in the same minute is noise that makes the feature
look automated rather than attentive.

`coalesce(trim(c.email), '') <> ''` even though the endpoint already refuses a
guardian with no email. The endpoint checks at the moment of choosing; a contact
can be edited afterwards, and a sweep that selected a blank address would try,
fail and retry it every minute for six hours.
"""


_PENDING_ARRIVED_NOTICE: Final = text(
    f"""
    select j.journey_id, c.email as guardian_email, c.name as guardian_name,
           j.ended_at, {_TRAVELLER}
      from public.journeys j
      {_GUARDIAN_FOR}
     where j.state = 'arrived'
       and j.arrived_notice_at is null
       and j.ended_at >= :backlog_cutoff
       and coalesce(trim(c.email), '') <> ''
     order by j.ended_at
     limit 200
    """
)
"""
Journeys that arrived and whose guardian has not been told.

`state = 'arrived'` only. A cancelled journey gets no message, and that is a
decision rather than an omission: "she changed her mind" is not something a
guardian needs emailing about, and `cancel` is also what leaving route mode
calls -- so a notice here would fire every time somebody closed the route card.

The silence is also honest. JG2 and JG3 exist to tell the difference between
"got there" and "stopped telling us", and a cancelled journey is neither: it is
"stopped on purpose", which needs nobody.
"""


_MARK_NOTICE = """
    update public.journeys
       set {column} = :now
     where journey_id = :journey_id
       and {column} is null
    returning journey_id
"""
"""
Stamp a notice as sent.

`and {column} is null` re-checked in the UPDATE, not just the SELECT: two
overlapping sweeps would otherwise both find the same row and both email the
guardian. The window is small and the duplicate is harmless-looking, which is
exactly why it would never be noticed.

Stamped **before** the send, like `_ask`. A crash between the two means the
guardian is not told; the other order means they may be told twice. For a
message that says "she set off", a duplicate is the more expensive mistake --
it is the first thing that makes somebody stop reading them.
"""

_MARK_STARTED: Final = text(_MARK_NOTICE.format(column="started_notice_at"))
_MARK_ARRIVED: Final = text(_MARK_NOTICE.format(column="arrived_notice_at"))


_ESCALATE = """
    update public.journeys
       set escalation_state = '{to_state}',
           {to_column} = :now
     where state = 'active'
       and escalation_state = '{from_state}'
       -- The gate. `JOURNEY_GUARDIAN.md` §7: "every step past the first
       -- requires a recorded non-response with a timestamp."
       --
       -- `{from_column}` IS that timestamp -- the moment the previous ring
       -- happened -- and the two conditions together are the record: the ring
       -- happened long enough ago, and nothing has been answered since. One
       -- without the other is not a non-response: a question asked four
       -- seconds ago is unanswered because nobody has had time.
       and {from_column} <= :cutoff
       and (answered_at is null or answered_at < {from_column})
       -- Not already done. Re-checked in the UPDATE and not only in a SELECT,
       -- because two overlapping sweeps would otherwise both escalate the same
       -- journey -- and at the last rung that means somebody's entire contact
       -- list mailed twice.
       and {to_column} is null
    returning journey_id, user_id
"""
"""
One forward step up the ladder, as a template.

Three statements of the same shape rather than three hand-written ones. The
alternative is the same five conditions copied twice with two column names
changed, which is how one copy ends up missing the `answered_at` clause -- and a
missing `answered_at` clause at the top rung emails somebody's whole contact
list about a journey that was answered.

Formatted rather than parameterised because a column name cannot be a bind
parameter in Postgres. The values interpolated are module constants from
`models/journey.py`, never anything from a request.
"""


def _escalation_step(from_state: str, to_state: str) -> Any:
    """Compile the statement that moves `from_state` one rung to `to_state`."""
    return text(
        _ESCALATE.format(
            from_state=from_state,
            to_state=to_state,
            from_column=ESCALATION_RECORDED_AT[from_state],
            to_column=ESCALATION_RECORDED_AT[to_state],
        )
    )


_REPEAT_THE_QUESTION: Final = _escalation_step(
    ESCALATION_CHECK_IN_SENT, ESCALATION_CHECK_IN_REPEATED
)
"""
Ring two: ask the same person again, louder in nothing but persistence.

Still only the traveller's own phone. `JOURNEY_GUARDIAN.md` §1 is explicit about
why this ring exists at all -- *"the first check-in is a liveness test, not just
a question"* -- and a second push is the cheapest possible way to tell a phone
that was merely in a pocket from one that is gone. A signal gap costs one more
buzz, not a message to somebody's family.
"""


_TELL_THE_GUARDIAN: Final = _escalation_step(
    ESCALATION_CHECK_IN_REPEATED, ESCALATION_CONTACTS_NOTIFIED
)
"""
Ring three: the second person, with a location.

The first ring that involves anybody else, and the first that carries a
position. Two pushes to her own phone have gone unanswered across at least ten
minutes, which is the recorded evidence the concept document requires before
widening the circle by one.
"""

# There is no ring four. The ladder ends at the guardian, deliberately -- see
# `_escalate_by_email`. `full_sos` remains a legal value of `escalation_state`
# because journeys reached it before this was removed and those rows are still
# read, answered and rendered; nothing climbs to it any more.


_ESCALATION_RECIPIENTS: Final = text(
    f"""
    select j.journey_id, j.destination_label, j.started_at, {_TRAVELLER},
           extensions.ST_Y(j.last_position::extensions.geometry) as last_lat,
           extensions.ST_X(j.last_position::extensions.geometry) as last_lon,
           j.last_position_at,
           extensions.ST_Y(j.origin::extensions.geometry) as origin_lat,
           extensions.ST_X(j.origin::extensions.geometry) as origin_lon,
           c.email as guardian_email
      from public.journeys j
      {_GUARDIAN_FOR}
     where j.journey_id = :journey_id
    """
)
"""
Everything an escalation message needs, for one journey.

**The only query in this module that reads `last_position` or `origin`**, and
that is the whole privacy design: the started and arrived notices select
neither, and `guardian.py`'s signatures for those two messages cannot accept a
position at all. Two independent reasons a location cannot reach a calm message.

`origin` is here because of what the first real device run showed: a journey can
run for twenty minutes, send heartbeats the whole time, and still have no
`last_position`. The navigator drops any fix worse than `MAX_ACCURACY_M` (100 m)
before anything sees it -- correct for snapping a route, and indoors or in a
basement that is every fix -- so the phone honestly reports "still going" with
nowhere attached. The escalation email then had no point in it at all, which is
the least useful version of the most important message this product sends.

The start point needs no collecting: `origin` is `not null` on every journey
since JG1, because the route was planned from it. So the fallback adds no data,
no write and no new privacy surface -- it reads a column that is already in the
row, in the one query that only runs when a guardian exists and an escalation is
already being sent. A journey with no guardian still has no position read about
it, because this query inner-joins the contact.

It is a **fallback and never a substitute**: a real fix always wins, and the
message says which one it is holding. See `escalation_message`.
"""

# The query that read a whole contact list is gone with the ring that used it.
# Every remaining statement in this module reads **one** contact row, the
# guardian, through `c.id = j.guardian_contact_id`.


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
            (
                "due",
                "sent",
                "failed",
                "no_device",
                "unanswered",
                # JG3. One counter per notice kind rather than one "emails"
                # total: a run that told four guardians somebody set off and
                # nobody that they arrived is a different situation from the
                # reverse, and "4" cannot tell them apart.
                "started_notices",
                "arrived_notices",
                "notices_failed",
                # One counter per ring. A single "escalations" total could not
                # distinguish four people being asked twice from four guardians
                # being emailed, and those are the two most different outcomes
                # this agent has.
                "repeated",
                "guardians_told",
                # Climbed, with nobody to tell. A guardianless journey is the
                # default kind, so this is an ordinary outcome and keeping it out
                # of `notices_failed` is what lets that number mean "go and
                # look".
                "nobody_to_tell",
            ),
            0.0,
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

            # Branches 3 and 4. JG3's two calm messages. Neither carries a
            # location and neither can: see `journeys/guardian.py`, where the
            # signatures have no parameter for one.
            cutoff = {"backlog_cutoff": ctx.now - NOTICE_BACKLOG}

            for row in (await ctx.db.execute(_PENDING_STARTED_NOTICE, cutoff)).all():
                ok = await self._notify(
                    ctx,
                    mark=_MARK_STARTED,
                    journey_id=row.journey_id,
                    to=row.guardian_email,
                    message=started_message(
                        traveller=row.traveller,
                        destination=row.destination_label,
                        due_by=row.deadline_at,
                    ),
                )
                if ok is None:
                    continue
                metrics["started_notices" if ok else "notices_failed"] += 1.0

            for row in (await ctx.db.execute(_PENDING_ARRIVED_NOTICE, cutoff)).all():
                ok = await self._notify(
                    ctx,
                    mark=_MARK_ARRIVED,
                    journey_id=row.journey_id,
                    to=row.guardian_email,
                    message=arrived_message(traveller=row.traveller, at=row.ended_at),
                )
                if ok is None:
                    continue
                metrics["arrived_notices" if ok else "notices_failed"] += 1.0

            # Branches 5, 6, 7 -- the ladder. In order, and in one pass, so a
            # journey can climb at most one rung per sweep: `_REPEAT_THE_QUESTION`
            # sets `check_in_repeated_at = ctx.now`, and `_TELL_THE_GUARDIAN`'s
            # gate needs it `<= ctx.now - CHECK_IN_WINDOW`. The same clock makes
            # "one step at a time" fall out of the arithmetic rather than needing
            # a flag.
            gate = {"now": ctx.now, "cutoff": ctx.now - CHECK_IN_WINDOW}

            # Ring two. Still only her own phone -- see the statement's note.
            for row in (await ctx.db.execute(_REPEAT_THE_QUESTION, gate)).all():
                logger.warning("journey %s is being asked a second time", row.journey_id)
                sent = await self._push_again(
                    ctx, transport=transport, journey_id=row.journey_id, user_id=row.user_id
                )
                if sent is None:
                    metrics["no_device"] += 1.0
                elif sent:
                    metrics["repeated"] += 1.0
                else:
                    metrics["failed"] += 1.0

            # Ring three. The first ring that tells anybody else, and the first
            # that carries a location.
            #
            # `None` is "there was nobody to tell", which is not a failure: a
            # journey with no guardian still climbs, because the rungs are the
            # record of what was asked and ignored, and nothing is wrong when
            # that record has no audience. Counting it as `notices_failed` --
            # which it was until the journey screen made the distinction
            # visible -- would make every guardianless escalation look like a
            # broken sweep, and `notices_failed` is the number that says whether
            # to go looking. Same three-way convention as `_push_again`.
            for row in (await ctx.db.execute(_TELL_THE_GUARDIAN, gate)).all():
                told = await self._escalate_by_email(ctx, journey_id=row.journey_id)
                if told is None:
                    metrics["nobody_to_tell"] += 1.0
                elif told:
                    metrics["guardians_told"] += 1.0
                else:
                    metrics["notices_failed"] += 1.0

            # There is no ring four. `contacts_notified` is where the ladder
            # stops: the person who was named gets told, and the circle widens
            # no further without somebody deciding to widen it.

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

    async def _push_again(
        self,
        ctx: AgentContext,
        *,
        transport: PushTransport,
        journey_id: object,
        user_id: object,
    ) -> bool | None:
        """
        Ring two: the same question, to the same phone, a second time.

        Separate from `_ask` and deliberately so, even though the push is
        identical. `_ask` also moves `normal -> check_in_sent`; the state here
        has already been moved by `_REPEAT_THE_QUESTION`, and calling `_ask`
        would try to move it again from the wrong starting state and silently
        match nothing.

        `None` when there is no registered device -- the same meaning as in
        `_ask`, so the caller's metric handling is the same. A phone with no
        token still climbs the ladder: it has to, because the thing being
        escalated is precisely the absence of an answer, and a person with no
        push token is the person least likely to give one.
        """
        tokens = (await ctx.db.execute(_DEVICES, {"user_id": user_id})).scalars().all()
        if not tokens:
            logger.info("journey %s is due a second ask but has no device", journey_id)
            return None

        message = compose_check_in(journey_id=str(journey_id))
        receipts = await transport.send([(token, message) for token in tokens])
        return any(receipt.ok for receipt in receipts)

    async def _escalate_by_email(
        self,
        ctx: AgentContext,
        *,
        journey_id: object,
    ) -> bool | None:
        """
        Ring three, and the last one: tell the guardian, with a location.

        The only sender in this module that carries a position, and the only one
        that reads `last_position`. `guardian.py::escalation_message` is the only
        composer that accepts one -- the other two have no parameter for it -- so
        a location cannot reach a calm notice even by mistake.

        **One recipient, always.** This took an `everyone` switch that widened
        the same send to every contact with an address, and that ring is gone:
        the person who was named is the person who is told. Widening the circle
        past them is a decision somebody should make while reading the email,
        not one a timer makes four rungs into a ladder that began with a missed
        tap.

        Returns whether anything was sent, or `None` for "there was nobody to
        tell" -- a journey with no guardian, which is the default and a perfectly
        ordinary journey. The caller counts that separately from a failure,
        because a sweep where ten guardianless journeys climbed is healthy and a
        sweep where ten sends failed is not.

        The state has already been moved by the caller's UPDATE and is **not**
        rolled back on a failed send, for the reason `_ask` gives at length: a
        journey left on the lower rung would be retried every minute, and the
        ladder would never finish climbing.
        """
        detail = (
            await ctx.db.execute(_ESCALATION_RECIPIENTS, {"journey_id": journey_id})
        ).one_or_none()
        if detail is None:
            # The inner join found no guardian -- the contact was deleted between
            # the escalation and this read, and `on delete set null` turned the
            # reference into nothing. Nobody to tell, and nothing is wrong.
            logger.info("journey %s escalated but has no guardian to tell", journey_id)
            return None

        last_seen = None
        if detail.last_lat is not None and detail.last_position_at is not None:
            last_seen = Position(
                latitude=detail.last_lat,
                longitude=detail.last_lon,
                at=detail.last_position_at,
            )

        # Where the journey began, used only when there is no fix at all. Both
        # are passed and the message picks: a real heartbeat always wins, and
        # the two are described differently because they are different claims --
        # "last reported from here" against "set off from here". Conflating them
        # would put a point an hour stale in front of somebody reading it as
        # current, which is worse than the honest "we do not know".
        started_from = None
        if detail.origin_lat is not None:
            started_from = Position(
                latitude=detail.origin_lat,
                longitude=detail.origin_lon,
                at=detail.started_at,
            )

        recipients = [detail.guardian_email]

        message = escalation_message(
            traveller=detail.traveller,
            destination=detail.destination_label,
            started_at=detail.started_at,
            last_seen=last_seen,
            started_from=started_from,
        )

        if ctx.dry_run:
            logger.info(
                "[dry-run] would escalate journey %s to %d recipient(s): %s",
                journey_id,
                len(recipients),
                message.subject,
            )
            return True

        logger.warning(
            "escalating journey %s to %d recipient(s)", journey_id, len(recipients)
        )
        return await email_service.send_guardian_message(
            to_emails=recipients,
            subject=message.subject,
            body=message.body,
            html=message.html,
        )

    async def _notify(
        self,
        ctx: AgentContext,
        *,
        mark: Any,
        journey_id: object,
        to: str,
        message: GuardianMessage,
    ) -> bool | None:
        """
        Email one guardian and stamp the journey as told.

        `None` when another sweep got there first -- the `is null` in `mark`
        matched nothing, so somebody else is sending this one and it must not be
        counted or sent twice.

        **Stamped before the send**, like `_ask`, and for a sharper reason here.
        A crash between the two means the guardian is never told about this
        journey. The other order means they may be told twice, and a duplicate
        "she has started a journey" is the single most effective way to teach
        somebody that these messages are noise. Of the two failures, silence on
        one journey costs less than a guardian who stops reading.

        A dry run sends nothing and the rollback at the end of `run` undoes the
        stamp, so a rehearsal neither mails anybody nor marks anything.
        """
        claimed = (
            await ctx.db.execute(mark, {"journey_id": journey_id, "now": ctx.now})
        ).one_or_none()
        if claimed is None:
            return None

        if ctx.dry_run:
            logger.info(
                "[dry-run] would email %s: %s", to, message.subject
            )
            return True

        sent = await email_service.send_guardian_message(
            to_emails=[to],
            subject=message.subject,
            body=message.body,
            html=message.html,
        )
        if not sent:
            # The stamp is rolled forward anyway -- see above. Logged at warning
            # because this is a guardian who believes they are being watched
            # over and is not.
            logger.warning("could not email the guardian for journey %s", journey_id)
        return sent

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
