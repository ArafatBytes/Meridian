"""
Journey Guardian wire shapes. JG1, extended by JG2.

What the app sends when someone presses Start, what it reads back when the app
launches, and -- since JG2 -- the one number a heartbeat carries.

There is still no guardian to name and no contact to notify; those are JG3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class JourneyStart(BaseModel):
    """
    The journey being started, as the route card knows it.

    Everything here comes from state the map screen already has: the two
    endpoints it routed between, the label in the destination field, and the
    selected `RouteResponse`. Nothing is computed on the client that the server
    needs to trust -- `eta_at` in particular is derived server-side from
    `started_at + duration_minutes`, because a clock the client sets is a
    deadline the client can move, and from JG2 onward that deadline is the
    feature.

    `deadline_minutes` is the one exception, and it is a narrow one: the person
    is allowed to choose how long they are giving themselves, because the router
    does not know they are stopping for food. What they cannot do is choose where
    that lands -- the server reads the minutes, clamps them and computes the
    instant from its own clock. See `app/journeys/deadline.py`.
    """

    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)

    #: What the person called the place. Trimmed and capped rather than
    #: validated: it is whatever was in the search box, including a POI name
    #: from a map tap, and it is only ever displayed back to its own author.
    destination_label: str = Field(..., min_length=1, max_length=200)

    route_id: str | None = Field(None, max_length=200)
    route_profile: Literal["driving", "foot"]

    distance_km: float = Field(..., ge=0, le=10_000)
    duration_minutes: float = Field(..., ge=0, le=24 * 60)
    safety_score: float | None = Field(None, ge=0, le=100)

    #: Minutes from now, as chosen at start. `None` means the person accepted
    #: the default, which is the route's own ETA plus the grace period.
    #:
    #: The bounds here are the wire's sanity check and not the policy: the real
    #: clamp is `MIN_DEADLINE`/`MAX_DEADLINE` in `journeys/deadline.py`, and it
    #: is applied to the default as well as to a choice. Two bounds rather than
    #: one because a schema that accepted 50,000 would make the clamp the only
    #: thing standing between a typo and a journey due next Tuesday.
    deadline_minutes: int | None = Field(None, ge=1, le=24 * 60)


class JourneyHeartbeat(BaseModel):
    """
    The phone saying it is still going, and roughly how much is left.

    One number, and deliberately no position. JG2 has no reader for a location:
    the check-in goes to the person's own phone, and the only message that needs
    a last known position is the escalation JG3 sends to somebody else. See the
    migration header.

    `remaining_seconds` is the navigator's own live estimate -- `remainingSeconds`
    in `useNavigation` -- which is computed from measured GPS progress rather than
    from the route's original promise. That is what makes a jam extend the
    deadline honestly: the phone says "still going, longer than I thought", and
    the clock follows.
    """

    remaining_seconds: float = Field(..., ge=0, le=24 * 60 * 60)


class JourneyResponse(BaseModel):
    """
    A journey as the app reads it. The whole visible output of JG1 is one
    sentence built from `duration_minutes` and `destination_label` -- "12 min to
    Mirpur" -- plus the two coordinates needed to put the route back on screen.
    """

    journey_id: str
    state: Literal["active", "arrived", "cancelled"]

    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    destination_label: str

    route_id: str | None = None
    route_profile: str
    distance_km: float
    duration_minutes: float
    safety_score: float | None = None

    started_at: datetime
    eta_at: datetime
    ended_at: datetime | None = None

    # ---- JG2: the clock, and the one question ----------------------------

    #: When the server expects you. Moved only by a heartbeat or an answer.
    deadline_at: datetime

    #: `normal` or `check_in_sent`. JG3 adds the rest of the chain.
    escalation_state: Literal["normal", "check_in_sent"]

    #: When the current question was asked, when it was answered, and when the
    #: sweep observed it go unanswered. All three are history rather than state:
    #: `answered_at` survives the return to `normal`, which is why the app
    #: compares it against `check_in_sent_at` rather than reading it alone.
    check_in_sent_at: datetime | None = None
    answered_at: datetime | None = None
    unanswered_at: datetime | None = None

    last_heartbeat_at: datetime | None = None
