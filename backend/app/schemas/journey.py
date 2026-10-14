"""
Journey Guardian wire shapes. JG1.

Two of them: what the app sends when someone presses Start, and what it reads
back when the app launches. Nothing else, because JG1 has nothing else -- no
deadline to report, no check-in to answer, no guardian to name.
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
