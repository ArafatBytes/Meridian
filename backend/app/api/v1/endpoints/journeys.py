"""
JG1 — the journey that survives. JG2 — the deadline, and one tap to answer.

    POST /journeys                  start one, with a deadline
    GET  /journeys/active           the caller's open journey, or null
    POST /journeys/{id}/arrive      active -> arrived
    POST /journeys/{id}/cancel      active -> cancelled
    POST /journeys/{id}/heartbeat   still going, about N seconds left   (JG2)
    POST /journeys/{id}/check-in    "I'm fine"                          (JG2)

**Nothing here tells anybody else anything.** The check-in goes to the person's
own phone and the answer comes back to this table; there is no guardian, no
contact and no message leaving the account. That is JG3. What JG2 adds is a
clock, one question, and a record of whether it was answered.

The two JG2 routes are both idempotent and both no-ops on a journey that is not
active, for the same reason the JG1 terminals are: each is reachable from a
background timer or a lock-screen tap that cannot know what the journey did since
the screen was drawn.

`GET /journeys/active` is the whole point of the phase from the app's side. It is
the call the map screen makes on launch, and the one sentence it produces --
"journey in progress, 12 min to Mirpur" -- is the demo.

Raw SQL rather than the ORM
---------------------------
`origin` and `destination` are PostGIS geographies. Reading one through the ORM
hands back WKB that then needs decoding, so every read in this project that wants
a latitude and a longitude does `ST_Y`/`ST_X` in the query instead -- see
`endpoints/sos.py`'s history read and `scoring/surface_db.py`. The writes are
raw for the same reason and for consistency: one idiom in a small module beats
two. `app/models/journey.py` stays the home of the state machine, which is the
part worth having in Python.

`extensions` is the schema PostGIS lives in on this Supabase project.
"""
from __future__ import annotations

import logging
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.journeys.deadline import (
    ANSWER_EXTENSION,
    MAX_DEADLINE,
    heartbeat_offset,
    leash,
    start_offset,
)
from app.models.journey import STATE_ARRIVED, STATE_CANCELLED, may_transition
from app.schemas.journey import JourneyHeartbeat, JourneyResponse, JourneyStart

logger = logging.getLogger(__name__)

router = APIRouter()


# The columns every response is built from. `ST_Y` is latitude and `ST_X` is
# longitude -- POINT is (x, y), which is (longitude, latitude), and getting that
# pair the wrong way round puts Dhaka in the Indian Ocean.
_COLUMNS: Final = """
    journey_id, state, destination_label, route_id, route_profile,
    distance_km, duration_minutes, safety_score,
    started_at, eta_at, ended_at,
    deadline_at, escalation_state,
    check_in_sent_at, answered_at, unanswered_at, last_heartbeat_at,
    extensions.ST_Y(origin::extensions.geometry)      as origin_lat,
    extensions.ST_X(origin::extensions.geometry)      as origin_lon,
    extensions.ST_Y(destination::extensions.geometry) as dest_lat,
    extensions.ST_X(destination::extensions.geometry) as dest_lon
"""


_INSERT: Final = text(
    f"""
    insert into public.journeys (
        user_id, origin, destination, destination_label,
        route_id, route_profile, distance_km, duration_minutes, safety_score,
        started_at, eta_at, deadline_at, leash_seconds
    ) values (
        :user_id,
        extensions.ST_SetSRID(extensions.ST_MakePoint(:origin_lon, :origin_lat), 4326)::extensions.geography,
        extensions.ST_SetSRID(extensions.ST_MakePoint(:dest_lon, :dest_lat), 4326)::extensions.geography,
        :destination_label,
        :route_id, :route_profile, :distance_km, :duration_minutes, :safety_score,
        now(),
        -- Derived from the server's own clock and never taken from the request.
        -- This is the route's promise, frozen: it is NOT the deadline, and JG2's
        -- migration corrected the JG1 comment here that said it would become one.
        now() + make_interval(secs => :duration_seconds),

        -- The deadline. Same clock, and the offset comes from
        -- `journeys/deadline.py::start_offset`, which is where the grace period
        -- and the clamp live. A clock the client sets is a deadline the client
        -- can move, so what the request carries is a number of minutes and the
        -- instant is computed here.
        now() + make_interval(secs => :deadline_seconds),

        -- NULL when the route's own ETA was accepted. See `deadline.leash`:
        -- this is what stops a heartbeat handing somebody ten minutes they did
        -- not ask for.
        :leash_seconds
    )
    returning {_COLUMNS}
    """
)


_SELECT_ACTIVE: Final = text(
    f"""
    select {_COLUMNS}
    from public.journeys
    where user_id = :user_id and state = 'active'
    -- `idx_journeys_one_active_per_user` makes this at most one row. The order
    -- and the limit are belt and braces for a database where that index has not
    -- been applied yet, so a stale schema degrades to "the newest one" rather
    -- than to a 500.
    order by started_at desc
    limit 1
    """
)


_END: Final = text(
    f"""
    update public.journeys
       set state = :state, ended_at = now()
     where journey_id = :journey_id
       and user_id = :user_id
       -- The transition is enforced here rather than read-then-written: two
       -- taps on End, or an arrival firing while the user presses the cross,
       -- would otherwise both pass a Python check and the second would rewrite
       -- `ended_at`. No row updated means it was not active, which the caller
       -- below turns into the state it already has.
       and state = 'active'
    returning {_COLUMNS}
    """
)


_SELECT_ONE: Final = text(
    f"""
    select {_COLUMNS}
    from public.journeys
    where journey_id = :journey_id and user_id = :user_id
    """
)


# A journey started while another is open cancels it. See `_start` for why that
# is the behaviour rather than a 409.
_CANCEL_ACTIVE: Final = text(
    """
    update public.journeys
       set state = 'cancelled', ended_at = now()
     where user_id = :user_id and state = 'active'
    returning journey_id
    """
)


# ---------------------------------------------------------------------------
# JG2
# ---------------------------------------------------------------------------

_HEARTBEAT: Final = text(
    f"""
    update public.journeys
       set last_heartbeat_at = now(),
           deadline_at = case
               -- Only while nothing has been asked. Once a check-in is out, a
               -- phone whose GPS is still ticking in a bag must not be able to
               -- talk its way out of a question a person has to answer.
               when escalation_state = 'normal' then least(
                   -- Forward only. Evaluated here, against the row, rather than
                   -- in Python against a value read a moment ago: two heartbeats
                   -- racing would otherwise let the older proposal land last and
                   -- pull the deadline backwards.
                   greatest(
                       deadline_at,
                       now() + make_interval(secs => least(
                           :slide_seconds,
                           -- The leash the person chose, when they chose one.
                           -- Without this cap a two-minute leash became twelve
                           -- the first time this ran on a phone: the proposal
                           -- carries a full grace period on top of the route's
                           -- remainder, and `greatest` took it because it was
                           -- later. `coalesce` rather than a second branch, so
                           -- the default -- no leash -- is the proposal itself.
                           coalesce(leash_seconds, :slide_seconds)
                       ))
                   ),
                   -- The ceiling. Without it a steady "about twenty minutes
                   -- left" from a stationary phone extends the deadline forever,
                   -- one minute at a time, and the journey is never due.
                   started_at + make_interval(secs => :ceiling_seconds)
               )
               else deadline_at
           end
     where journey_id = :journey_id
       and user_id = :user_id
       and state = 'active'
    returning {_COLUMNS}
    """
)


_CHECK_IN: Final = text(
    f"""
    update public.journeys
       set escalation_state = 'normal',
           answered_at = now(),
           unanswered_at = null,
           -- Capped by the leash, for the same reason the heartbeat is. Answering
           -- buys ANSWER_EXTENSION, but somebody who said "two minutes" must not
           -- be handed fifteen for tapping the button -- that is the heartbeat
           -- bug of 20261015140000__journey_leash.sql wearing a different hat,
           -- and it was found on the same row, one path over. `coalesce` leaves
           -- the default chip (no leash) at the full extension, which is the
           -- common case and unchanged.
           deadline_at = least(
               now() + make_interval(secs => least(
                   :extension_seconds,
                   coalesce(leash_seconds, :extension_seconds)
               )),
               started_at + make_interval(secs => :ceiling_seconds)
           )
     where journey_id = :journey_id
       and user_id = :user_id
       and state = 'active'
       -- There has to be a question to answer. `journeys_answered_after_asked`
       -- says the same thing at the table level; this is what turns it into a
       -- 409 instead of an IntegrityError, and what stops an answer sent out of
       -- nowhere from buying an extension.
       and escalation_state = 'check_in_sent'
    returning {_COLUMNS}
    """
)


def _response(row: Any) -> JourneyResponse:
    return JourneyResponse(
        journey_id=str(row.journey_id),
        state=row.state,
        origin_latitude=float(row.origin_lat),
        origin_longitude=float(row.origin_lon),
        destination_latitude=float(row.dest_lat),
        destination_longitude=float(row.dest_lon),
        destination_label=row.destination_label,
        route_id=row.route_id,
        route_profile=row.route_profile,
        distance_km=float(row.distance_km),
        duration_minutes=float(row.duration_minutes),
        safety_score=None if row.safety_score is None else float(row.safety_score),
        started_at=row.started_at,
        eta_at=row.eta_at,
        ended_at=row.ended_at,
        deadline_at=row.deadline_at,
        escalation_state=row.escalation_state,
        check_in_sent_at=row.check_in_sent_at,
        answered_at=row.answered_at,
        unanswered_at=row.unanswered_at,
        last_heartbeat_at=row.last_heartbeat_at,
    )


@router.post("", response_model=JourneyResponse, status_code=status.HTTP_201_CREATED)
async def start_journey(
    body: JourneyStart,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse:
    """
    Start a journey.

    **Any journey already open is cancelled first**, rather than this returning a
    409. The force-stop that this phase exists to survive is exactly the case
    where an active row is left behind with nobody to close it -- so a 409 would
    mean the Start button stops working until the user finds the End button for a
    journey the app is no longer showing. Pressing Start is an unambiguous
    statement about where the person is going now, and the previous journey
    ending as `cancelled` rather than `arrived` is the truth about it.

    `idx_journeys_one_active_per_user` is what makes a bug in this sequence a
    failed insert instead of two live journeys -- which, from JG3 onward, would
    mean two deadlines and two guardians watching one person.
    """
    user_id = current_user["user_id"]

    superseded = (await db.execute(_CANCEL_ACTIVE, {"user_id": user_id})).scalars().all()
    if superseded:
        logger.info(
            "journey start superseded %d open journey(s) for user %s",
            len(superseded),
            user_id,
        )

    row = (
        await db.execute(
            _INSERT,
            {
                "user_id": user_id,
                "origin_lat": body.origin_latitude,
                "origin_lon": body.origin_longitude,
                "dest_lat": body.destination_latitude,
                "dest_lon": body.destination_longitude,
                "destination_label": body.destination_label.strip(),
                "route_id": body.route_id,
                "route_profile": body.route_profile,
                "distance_km": body.distance_km,
                "duration_minutes": body.duration_minutes,
                "safety_score": body.safety_score,
                "duration_seconds": body.duration_minutes * 60.0,
                "deadline_seconds": start_offset(
                    duration_minutes=body.duration_minutes,
                    chosen_minutes=body.deadline_minutes,
                ).total_seconds(),
                "leash_seconds": (
                    None
                    if (chosen := leash(chosen_minutes=body.deadline_minutes)) is None
                    else chosen.total_seconds()
                ),
            },
        )
    ).one()

    return _response(row)


@router.get("/active", response_model=JourneyResponse | None)
async def active_journey(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse | None:
    """
    The caller's open journey, or `null`.

    `null` rather than a 404: having no journey in progress is the ordinary
    answer, not a missing resource, and the app calls this on every launch. A 404
    here would put an error in the log on every cold start of every install.
    """
    row = (await db.execute(_SELECT_ACTIVE, {"user_id": current_user["user_id"]})).one_or_none()
    return None if row is None else _response(row)


async def _end(journey_id: str, state: str, db: AsyncSession, user_id: str) -> JourneyResponse:
    """
    Move an active journey to a terminal state.

    Idempotent on purpose. Ending a journey that is already in the state asked
    for returns it unchanged, because both ways of reaching this are things a
    user can do twice: tapping End while the request is in flight, and an
    arrival detected by the navigator at the same moment the user closes the
    route card. The alternative is an error dialog about something that already
    happened.
    """
    row = (
        await db.execute(_END, {"journey_id": journey_id, "user_id": user_id, "state": state})
    ).one_or_none()
    if row is not None:
        return _response(row)

    # Nothing updated: either it was not active, or it is not this caller's.
    existing = (
        await db.execute(_SELECT_ONE, {"journey_id": journey_id, "user_id": user_id})
    ).one_or_none()

    # 404 rather than 403 on someone else's journey: whether a given journey id
    # exists is not this caller's business either. Same choice as
    # `casework._owned_draft`.
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such journey")

    if existing.state == state:
        return _response(existing)

    # A real conflict: arriving on a cancelled journey, or the reverse.
    # `may_transition` is consulted so the one definition of the state machine
    # decides, and the message names both states because the app's next move
    # depends on which one it is actually in.
    if not may_transition(existing.state, state):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This journey is {existing.state} and cannot become {state}",
        )

    # Unreachable unless the UPDATE lost a race it should not be able to lose.
    raise HTTPException(status.HTTP_409_CONFLICT, "Could not end this journey")


@router.post("/{journey_id}/arrive", response_model=JourneyResponse)
async def arrive(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse:
    """You got there. From JG2 onward this is also what stops the clock."""
    return await _end(journey_id, STATE_ARRIVED, db, current_user["user_id"])


@router.post("/{journey_id}/cancel", response_model=JourneyResponse)
async def cancel(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse:
    """
    You stopped, changed your mind, or went somewhere else.

    Distinct from `arrive` and it has to stay distinct: a journey that ends
    without arriving is the shape of the thing JG2 and JG3 care about, and
    collapsing the two states would throw away the only signal that separates
    "got home" from "stopped telling us".
    """
    return await _end(journey_id, STATE_CANCELLED, db, current_user["user_id"])


# ---------------------------------------------------------------------------
# JG2 — the clock
# ---------------------------------------------------------------------------


async def _not_active(journey_id: str, db: AsyncSession, user_id: str) -> HTTPException:
    """
    Why the UPDATE matched nothing, as the exception to raise.

    Shared by both JG2 routes because both are reached from places that cannot
    know the journey's current state -- a background timer and a notification
    action -- so "it already ended" has to be an ordinary answer rather than a
    500 or a lie.
    """
    existing = (
        await db.execute(_SELECT_ONE, {"journey_id": journey_id, "user_id": user_id})
    ).one_or_none()
    # 404 rather than 403 on someone else's journey, as in `_end`: whether a
    # given journey id exists is not this caller's business either.
    if existing is None:
        return HTTPException(status.HTTP_404_NOT_FOUND, "No such journey")
    return HTTPException(
        status.HTTP_409_CONFLICT,
        f"This journey is {existing.state} and is no longer running",
    )


@router.post("/{journey_id}/heartbeat", response_model=JourneyResponse)
async def heartbeat(
    journey_id: str,
    body: JourneyHeartbeat,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse:
    """
    The phone saying it is still going, and roughly how much is left.

    This is the only thing in the system that extends a deadline without a person
    pressing anything, and the asymmetry it creates is the whole design:

        a phone in a jam talks       -> the clock follows it
        a phone in a ditch does not  -> the clock runs out

    Silence never buys an extension, and not because anything checks for silence.
    There is simply no code path that moves a deadline on its own. Deleting this
    route would make every journey due exactly when it said it would be.

    Carries no position. JG2 has no reader for one -- the check-in goes to this
    person's own phone -- and the only message that needs a last known location
    is the escalation JG3 sends to somebody else.
    """
    row = (
        await db.execute(
            _HEARTBEAT,
            {
                "journey_id": journey_id,
                "user_id": current_user["user_id"],
                "slide_seconds": heartbeat_offset(
                    remaining_seconds=body.remaining_seconds
                ).total_seconds(),
                "ceiling_seconds": MAX_DEADLINE.total_seconds(),
            },
        )
    ).one_or_none()

    if row is None:
        raise await _not_active(journey_id, db, current_user["user_id"])
    return _response(row)


@router.post("/{journey_id}/check-in", response_model=JourneyResponse)
async def check_in(
    journey_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> JourneyResponse:
    """
    "I'm fine." The one tap this phase exists to make possible.

    Takes no body on purpose. There is exactly one answer in JG2 and it is
    affirmative, so a field saying which answer it was would have one legal
    value. JG6 is the phase that adds a second button -- the one that looks like
    this one and silently escalates instead -- and when it does, the difference
    has to be invisible on the wire as well as on the screen, which means a new
    route rather than a flag on this one.

    Answering returns the journey to `normal` and buys `ANSWER_EXTENSION` from
    now. It does not clear `check_in_sent_at`: that is the history of what
    happened on this trip, and JG3's escalation reads it. It does clear
    `unanswered_at`, because that record belongs to the question just answered.

    409 when there is no question outstanding. An answer accepted out of nowhere
    would be a way to extend a deadline by replaying a notification action, which
    is the one thing a lock-screen button must not be.
    """
    row = (
        await db.execute(
            _CHECK_IN,
            {
                "journey_id": journey_id,
                "user_id": current_user["user_id"],
                "extension_seconds": ANSWER_EXTENSION.total_seconds(),
                "ceiling_seconds": MAX_DEADLINE.total_seconds(),
            },
        )
    ).one_or_none()

    if row is not None:
        return _response(row)

    existing = (
        await db.execute(
            _SELECT_ONE, {"journey_id": journey_id, "user_id": current_user["user_id"]}
        )
    ).one_or_none()
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such journey")
    if existing.state != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This journey is {existing.state} and is no longer running",
        )
    raise HTTPException(status.HTTP_409_CONFLICT, "Nothing to answer on this journey")
