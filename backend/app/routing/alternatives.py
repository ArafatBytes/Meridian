"""
Generating a route that avoids a flag, when OSRM will not offer one.

S12 asks for *"multi-route generation — OSRM alternatives, each scored, ranked"*, and
OSRM's own alternatives are not enough on their own. Measured against the local Bangladesh
graph on 2026-10-09, five Dhaka origin–destination pairs returned:

    Bangshal     -> Mirpur-10     1 route
    Mirpur-10    -> Banani        1 route
    Dhanmondi    -> Gulshan       2 routes
    Uttara       -> Bangshal      2 routes
    Airport      -> Jatrabari     2 routes

So roughly half the time there is nothing to rank, and **demo beat 4 is specifically
"ask for a route through a flagged corridor, get alternatives, each with a reason"**. A
beat that depends on the audience's origin and destination happening to be one of the lucky
pairs is not a beat.

More importantly, OSRM's alternatives are *geometric* — it offers them when a meaningfully
different road exists, with no idea that one of them passes a fire. An alternative generated
because of a flag is the only kind that can honestly carry the sentence
*"4 minutes longer, avoids two flagged corridors."*

---

## How it works

Take the worst **live** flag on the fastest route. Push a waypoint away from it,
perpendicular to the route, far enough to clear the flag's radius plus the scoring
corridor. Ask OSRM for `start → waypoint → end`. Keep the result only if it genuinely drops
that flag and is not absurdly longer.

**Chronic flags are excluded as detour targets.** Routing around a historical average is
not a thing a traveller wants: the chronic layer covers most of Dhaka with 2 km radii, so
"avoiding" one usually means avoiding the city, and the resulting detour would be justified
by a sentence that is technically true and practically useless. Live events — a fire, a
blockade, a procession — are what you detour around. This is the same reasoning that gives
chronic flags a reduced weight in `scorer.py`.

## Why the result is verified rather than trusted

OSRM snaps a waypoint to the nearest routable road, and the nearest road is sometimes the
one we were trying to leave. So the candidate is scored like any other and **discarded
unless the flag it was built to avoid is actually gone**. Returning a "safer alternative"
that passes the same fire would be worse than returning one route.
"""

from __future__ import annotations

import logging
import math
from typing import Final

from app.contracts.risk import IncidentKind, RiskFlag
from app.routing.osrm import OsrmRoute, Profile, fetch_routes_via
from app.scoring.geometry import distance_to_segment_m, haversine_m

logger = logging.getLogger(__name__)

__all__ = ["detour_waypoints", "worst_live_flag", "generate_detour"]

_CLEARANCE_MARGIN_M: Final[int] = 250
"""
Extra distance beyond the flag's radius plus the scoring corridor.

Without a margin the waypoint sits exactly on the corridor boundary, and OSRM snapping it
to the nearest road moves it back inside about as often as not. 250 m is roughly one Dhaka
block -- enough to land on a different road, little enough that the detour stays local.
"""

_MAX_OFFSET_M: Final[int] = 2_500
"""
Ceiling on how far the waypoint may be pushed.

A 2 km-radius flag would otherwise generate a waypoint kilometres off-route and OSRM would
dutifully return a journey through a different part of the city. Capped, because a detour
nobody would take is not an alternative.
"""

_MIN_SEVERITY_TO_DETOUR: Final[float] = 20.0
"""
Below this decayed severity, do not build a detour around it.

A flag at severity 8 is nearly expired; routing someone several minutes out of their way to
avoid it is worse advice than letting them pass it. This is also what stops the generator
firing on every route in the city.
"""

_METRES_PER_DEGREE_LAT: Final[float] = 111_320.0


def worst_live_flag(flags: list[RiskFlag]) -> RiskFlag | None:
    """
    The flag worth detouring around, or None.

    Live only -- `chronic` is excluded, see the module docstring -- and only above
    `_MIN_SEVERITY_TO_DETOUR`. Does not assume `flags` is sorted.
    """
    candidates = [
        flag
        for flag in flags
        if flag.kind != IncidentKind.CHRONIC and flag.severity_now >= _MIN_SEVERITY_TO_DETOUR
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda flag: flag.severity_now)


def _nearest_segment(
    flag: RiskFlag, path: list[tuple[float, float]]
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """The path segment closest to the flag, or None if the path is not a line."""
    if len(path) < 2:
        return None
    segments = list(zip(path, path[1:]))
    return min(
        segments,
        key=lambda seg: distance_to_segment_m(
            flag.lat, flag.lon, seg[0][0], seg[0][1], seg[1][0], seg[1][1]
        ),
    )


def detour_waypoints(
    flag: RiskFlag,
    path: list[tuple[float, float]],
    corridor_radius_m: int,
) -> list[tuple[float, float]]:
    """
    Up to two points to route through that clear `flag` -- one either side of the road.

    **Perpendicular to the route's local heading**, which is the whole correction here. The
    first version of this pushed away from the flag *towards the nearest path vertex*, and
    that fails on the case that matters most: a flag sitting **on** the road you are
    travelling. There is then no flag-to-vertex direction at all (the distance is zero), so
    it returned nothing — meaning no detour was ever generated for an obstruction actually
    on the route. A test caught it.

    Stepping sideways is also what a person does. You do not back away from a blocked
    junction along your approach; you take the next street over. So: find the segment
    nearest the flag, take its heading, rotate 90 degrees, and offset far enough to clear
    the flag's radius plus the scoring corridor.

    Both sides are returned because which one has a usable road is not knowable from here.
    `generate_detour` tries them in order and keeps the first that actually works.

    Empty when the path is not a line or the segment has no length -- a coincidence rather
    than an error.
    """
    segment = _nearest_segment(flag, path)
    if segment is None:
        return []

    (lat_a, lon_a), (lat_b, lon_b) = segment
    metres_per_deg_lon = math.cos(math.radians(flag.lat)) * _METRES_PER_DEGREE_LAT

    # Heading of the segment, in local metres.
    dx = (lon_b - lon_a) * metres_per_deg_lon
    dy = (lat_b - lat_a) * _METRES_PER_DEGREE_LAT
    length = math.hypot(dx, dy)
    if length < 1.0:
        return []

    # Rotate 90 degrees: (dx, dy) -> (-dy, dx). The opposite side is the negation.
    nx, ny = -dy / length, dx / length

    offset_m = min(
        float(_MAX_OFFSET_M),
        float(flag.radius_m + corridor_radius_m + _CLEARANCE_MARGIN_M),
    )

    return [
        (
            flag.lat + (ny * sign * offset_m) / _METRES_PER_DEGREE_LAT,
            flag.lon + (nx * sign * offset_m) / metres_per_deg_lon,
        )
        for sign in (1.0, -1.0)
    ]


async def generate_detour(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    profile: Profile,
    flag: RiskFlag,
    path: list[tuple[float, float]],
    corridor_radius_m: int,
) -> OsrmRoute | None:
    """
    A route from `start` to `end` that goes around `flag`, or None.

    Tries a waypoint on each side of the road and keeps the first result that genuinely
    clears the flag. Returns None rather than raising for every failure mode -- OSRM
    unreachable, no road near either waypoint, both detours passing the flag anyway. An
    alternative is a bonus; the primary route is already in hand and a failure here must
    not cost the caller its answer.

    **The result is verified, not trusted.** OSRM snaps a waypoint to the nearest routable
    road, and the nearest road is sometimes the one we were trying to leave. Offering a
    "safer alternative" that passes the same fire would be worse than offering one route.
    """
    for waypoint in detour_waypoints(flag, path, corridor_radius_m):
        try:
            routes = await fetch_routes_via(
                start=start, waypoints=[waypoint], end=end, profile=profile
            )
        except Exception as exc:
            logger.info("detour generation failed (%s: %s)", type(exc).__name__, exc)
            continue

        for candidate in routes:
            if _clears(flag, candidate.path, corridor_radius_m):
                logger.info(
                    "generated a detour avoiding %r (severity %.1f)",
                    flag.mobility_statement,
                    flag.severity_now,
                )
                return candidate

        logger.debug("a detour candidate still passed the flag; trying the other side")

    logger.info(
        "no detour cleared %r; offering one route rather than a misleading alternative",
        flag.mobility_statement,
    )
    return None


def _clears(flag: RiskFlag, path: list[tuple[float, float]], corridor_radius_m: int) -> bool:
    """Is `flag` outside the corridor of `path`? Point-to-segment, as the surfaces measure."""
    if len(path) < 2:
        return False
    return all(
        distance_to_segment_m(flag.lat, flag.lon, a[0], a[1], b[0], b[1]) > corridor_radius_m
        for a, b in zip(path, path[1:])
    )
