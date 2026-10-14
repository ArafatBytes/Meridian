"""
JG1 — the journey that survives.

    POST /journeys                 start one
    GET  /journeys/active          the caller's open journey, or null
    POST /journeys/{id}/arrive     active -> arrived
    POST /journeys/{id}/cancel     active -> cancelled

Four routes and no fifth. **Nothing here watches anything.** There is no
deadline, no check-in, no escalation and no background job reading this table.
The claim of this phase is survival and only survival: the row outlives the
process, so force-stopping the app mid-journey and reopening it finds the journey
still there. JG2 is what gives it a clock; JG3 is what gives it an audience.

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
from app.models.journey import STATE_ARRIVED, STATE_CANCELLED, may_transition
from app.schemas.journey import JourneyResponse, JourneyStart

logger = logging.getLogger(__name__)

router = APIRouter()


# The columns every response is built from. `ST_Y` is latitude and `ST_X` is
# longitude -- POINT is (x, y), which is (longitude, latitude), and getting that
# pair the wrong way round puts Dhaka in the Indian Ocean.
_COLUMNS: Final = """
    journey_id, state, destination_label, route_id, route_profile,
    distance_km, duration_minutes, safety_score,
    started_at, eta_at, ended_at,
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
        started_at, eta_at
    ) values (
        :user_id,
        extensions.ST_SetSRID(extensions.ST_MakePoint(:origin_lon, :origin_lat), 4326)::extensions.geography,
        extensions.ST_SetSRID(extensions.ST_MakePoint(:dest_lon, :dest_lat), 4326)::extensions.geography,
        :destination_label,
        :route_id, :route_profile, :distance_km, :duration_minutes, :safety_score,
        now(),
        -- Derived here, from the server's own clock, and never taken from the
        -- request. From JG2 onward this instant is the deadline, and a deadline
        -- the client sets is a deadline the client can move.
        now() + make_interval(secs => :duration_seconds)
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
