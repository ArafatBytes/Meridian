"""
Route generation: OSRM for the roads, the risk surface for the danger, `routing/` for
the judgement.

D06. This module used to be ~230 lines that did all of it inline, and five defects lived
here:

| Defect | What it was |
|---|---|
| 7 | hardcoded public OSRM demo server; `duration = dist / 30 km/h`; driving only |
| 8 | `select(CrimeReport)` with **no spatial predicate** — every row, then a nested Python loop |
| 6 | `avoid_high_crime_zones` and `max_crime_score` accepted and silently ignored |
| 11 | three scales for one quantity: 0–10 `crime_score`, 0–100 `safety_score`, `% Safe` |
| — | `_get_regional_risk()` — the police-statistics double count D02 left a note about |

What is left here is **orchestration only**: ask OSRM for candidates, ask the surface what
is on each, ask the scorer what that is worth, ask `explain.py` to say why, rank, filter,
return. Every decision lives in `app/routing/`, which is what lets all of it run unchanged
on `RISK_SURFACE_IMPL=seeded`.

---

## `_get_regional_risk` is gone, not fixed

D02 moved `scripts/crime_risk_model.json` into the risk surface as the chronic baseline
layer, so those same police statistics now arrive through `flags_near_path` and are scored
by the same arithmetic as everything else. Keeping the method would have counted regional
risk **twice**, from two code paths, and the symptom is a plausible-looking safety score
that is quietly wrong — the worst kind of bug to carry onto a stage, because nothing looks
broken.

It also had an independent bug worth recording now that the code is gone: it took `max()`
of `normalized_risk` across every overlapping police unit, and the dataset contains both
metropolitan units *and* the ranges that contain them. Every point in Dhaka therefore
scored **100.0 from `Dhaka Range`** instead of 58.9 from `DMP`. `app/scoring/chronic.py`
drops the range rows for exactly this reason and documents why.

## The straight-line fallback is labelled, not disguised

If OSRM is unreachable in both configurations, the service returns a single
great-circle estimate with `engine="straight-line"`. It is still scored against the risk
surface, so it is not useless — but it is not a route, it follows no road, and the client
must say so. The previous code generated two *simulated* paths, one with a sine-wave
"deviation", and returned them indistinguishably from real ones.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.risk import RiskFlag
from app.core.config import settings
from app.routing.alternatives import generate_detour, worst_live_flag
from app.routing.explain import explain_route
from app.routing.osrm import OsrmRoute, OsrmUnavailable, fetch_routes
from app.routing.scorer import ScoredPath, apply_filters, composite, score_path
from app.schemas.route import (
    Location,
    RouteFlag,
    RouteRequest,
    RouteResponse,
    RouteSegment,
)
from app.scoring.factory import get_risk_surface
from app.scoring.geometry import haversine_m

logger = logging.getLogger(__name__)

_STRAIGHT_LINE_POINTS = 24
"""
Points in the fallback estimate.

Enough that the corridor query has a line to work with and the drawn path does not look
like a single segment, few enough that it is obviously not a road.
"""

_ASSUMED_WALK_KMH = 4.8
"""
Walking speed, used in two places.

The straight-line fallback, where there is no graph to ask -- and **walking routes**, whose
durations OSRM cannot currently answer. See `_WALKING_NOTE`. 4.8 km/h is an ordinary adult
pace on level ground; Dhaka footpaths are not level ground, so this is mildly optimistic and
is labelled as an estimate rather than presented as OSRM's answer.
"""

_ASSUMED_DRIVE_KMH = 22.0
"""
Driving speed for the straight-line fallback only.

22 km/h rather than the 30 the deleted code assumed: a 30 km/h average across Dhaka is
optimistic to the point of being wrong. Any real route uses OSRM's own duration.
"""

_CONGESTION_NOTE = (
    "Driving times are estimated for Dhaka traffic. The road map only knows free-flow "
    "speeds, which would put this journey at roughly three times the speed anyone "
    "actually travels."
)
"""
Shown on the card, because a duration is a claim and this one is a calibration.

The honest version of the sentence is the second half: OSRM is not wrong, it is answering
"how long on an empty road". Measured free-flow on the Bangshal -> Mirpur-10 route was
**54.8 km/h**, median segment speed 56 km/h. Scaling it is the interim fix;
`osrm-customize --segment-speed-file` is the real one and needs traffic data this project
does not have.

The note is deliberately not shown on a `straight-line` fallback -- that route already
carries a louder caveat saying it is not a road route at all, and stacking two would bury
the more important one.
"""

_WALKING_NOTE = (
    "Walking directions use the driving road map, so the route may include a flyover or "
    "follow a one-way street. The time is an estimate at 4.8 km/h, not a measured walking "
    "duration."
)
"""
Surfaced to the user, not merely logged. Defect 7 asked for a walking profile and this is as
much of one as the graph can honestly support.

Measured 2026-10-09: a `/foot/` request against the local graph returned **7.03 km in 9
minutes** -- identical to the driving answer, because the graph is built from `car.lua` and
OSRM will answer a foot request from whatever graph it has. 47 km/h presented as a walk is
not an imprecision, it is a false statement on a screen, so the duration is recomputed here
and the path caveat is shown rather than hidden in a log line.

The real fix is a second graph built with `foot.lua`. That is a background task, not
demo-critical, and it is written down in `app/routing/osrm.py :: WALKING_GRAPH_CAVEAT`.
"""


class RouteService:
    """
    Orchestration. Holds no risk model, loads no JSON, runs no scoring arithmetic.

    The constructor is deliberately empty. It used to read `crime_risk_model.json` at
    import time for `_get_regional_risk`, which meant every process importing this module
    — including ones that never route — paid for a file read and held the model in memory.
    """

    @staticmethod
    def _to_route_flag(flag: RiskFlag) -> RouteFlag:
        return RouteFlag(
            flag_id=str(flag.flag_id),
            lat=flag.lat,
            lon=flag.lon,
            radius_m=flag.radius_m,
            mobility_statement=flag.mobility_statement,
            severity_now=round(flag.severity_now, 1),
            status=flag.status,
            source_count=flag.source_count,
            kind=flag.kind.value,
        )

    def _straight_line(
        self, request: RouteRequest, profile: str
    ) -> OsrmRoute:
        """
        A great-circle estimate, for when OSRM is unreachable in both configurations.

        Labelled `straight-line` so the client can say it is not a route. Still scored
        against the risk surface, because "we could not reach the routing engine but there
        is a fire on the direct line" is more useful than nothing.
        """
        start = (request.source.latitude, request.source.longitude)
        end = (request.destination.latitude, request.destination.longitude)
        path = [
            (
                start[0] + (end[0] - start[0]) * index / _STRAIGHT_LINE_POINTS,
                start[1] + (end[1] - start[1]) * index / _STRAIGHT_LINE_POINTS,
            )
            for index in range(_STRAIGHT_LINE_POINTS + 1)
        ]
        distance_m = haversine_m(*start, *end)
        speed_kmh = _ASSUMED_WALK_KMH if profile == "foot" else _ASSUMED_DRIVE_KMH
        return OsrmRoute(
            path=path,
            distance_m=distance_m,
            duration_s=(distance_m / 1000.0) / speed_kmh * 3600.0,
            engine="straight-line",
        )

    async def calculate_routes(
        self,
        request: RouteRequest,
        db: AsyncSession,
        *,
        at: datetime | None = None,
    ) -> list[RouteResponse]:
        """
        Candidate routes, scored against the risk surface and ranked.

        `at` threads the clock the same way `GET /risk/flags?as_of=` does, so a route can be
        scored against the surface as it will be later — the seam D09's forward-looking view
        needs. Defaults to now.
        """
        moment = at or datetime.now(tz=UTC)
        profile = "foot" if request.profile == "foot" else "driving"

        try:
            candidates = await fetch_routes(
                start=(request.source.latitude, request.source.longitude),
                end=(request.destination.latitude, request.destination.longitude),
                profile=profile,  # type: ignore[arg-type]  # narrowed above
            )
        except OsrmUnavailable as exc:
            logger.warning(
                "no routing engine answered (%s). Returning a straight-line estimate, "
                "labelled as such.",
                exc,
            )
            candidates = [self._straight_line(request, profile)]

        surface = get_risk_surface(db)

        scored: list[tuple[OsrmRoute, ScoredPath]] = []
        for candidate in candidates:
            scored.append((candidate, await score_path(surface, path=candidate.path, at=moment)))

        # Beat 4 needs something to compare. OSRM offers its own alternatives only when a
        # geometrically distinct road exists -- measured across five Dhaka pairs, about half
        # the time -- and it has no idea that one route passes a fire. So when there is only
        # one candidate and it passes a live flag worth avoiding, build the detour ourselves.
        # `generate_detour` verifies the result actually clears that flag and returns None
        # otherwise, so this can add an alternative but never a misleading one.
        if len(scored) == 1 and candidates[0].engine != "straight-line":
            primary_route, primary_score = scored[0]
            target = worst_live_flag(primary_score.flags)
            if target is not None:
                detour = await generate_detour(
                    start=(request.source.latitude, request.source.longitude),
                    end=(request.destination.latitude, request.destination.longitude),
                    profile=profile,  # type: ignore[arg-type]  # narrowed above
                    flag=target,
                    path=primary_route.path,
                    corridor_radius_m=settings.ROUTE_CORRIDOR_RADIUS_M,
                )
                if detour is not None:
                    scored.append(
                        (detour, await score_path(surface, path=detour.path, at=moment))
                    )

        # Durations, corrected before anything ranks on them -- `composite` trades safety
        # against time, so a wrong duration changes which route is recommended, not just
        # what the card says.
        #
        # Both corrections exist because OSRM answers from a car.lua graph with no traffic
        # data. For walking it answers the wrong question entirely (it returned 7.03 km in
        # 9 minutes -- 47 km/h presented as a walk). For driving it answers the right
        # question about the wrong world: 54.8 km/h average across central Dhaka, which is
        # free-flow and physically absurd here.
        notes: list[str] = []
        if profile == "foot":
            notes.append(_WALKING_NOTE)
            scored = [
                (
                    replace(
                        route,
                        duration_s=(route.distance_m / 1000.0) / _ASSUMED_WALK_KMH * 3600.0,
                    ),
                    path_score,
                )
                for route, path_score in scored
            ]
        else:
            factor = settings.ROUTE_CONGESTION_FACTOR
            if factor > 0 and factor != 1.0 and any(
                route.engine != "straight-line" for route, _ in scored
            ):
                notes.append(_CONGESTION_NOTE)
                scored = [
                    (
                        route
                        if route.engine == "straight-line"
                        else replace(route, duration_s=route.duration_s / factor),
                        path_score,
                    )
                    for route, path_score in scored
                ]

        fastest_s = min(candidate.duration_s for candidate, _ in scored)

        # Rank before filtering, so a relaxed filter still returns the best option first.
        ranked = sorted(
            scored,
            key=lambda pair: composite(pair[1].safety_score, pair[0].duration_s, fastest_s),
            reverse=True,
        )

        keep, filter_relaxed = apply_filters(
            [path_score for _, path_score in ranked],
            avoid_high_crime_zones=request.avoid_high_crime_zones,
            max_crime_score=request.max_crime_score,
        )
        surviving = [pair for pair, keeping in zip(ranked, keep, strict=True) if keeping]
        if not surviving:
            return []

        # What each route avoids, for the trade-off sentence.
        #
        # The comparison a traveller is making is against the option they would otherwise
        # take, so:
        #   * the recommended route is compared with everything else — "avoids 2 flagged
        #     corridors" means two flags that some alternative passes and it does not;
        #   * an alternative is compared with the recommended route — "4 minutes longer,
        #     avoids two flagged corridors" means two the recommended one passes and it
        #     does not.
        #
        # Getting this backwards would produce a sentence claiming a route avoids the flags
        # it is in fact the only one to pass, which reads perfectly and is a lie.
        flag_ids = [{flag.flag_id for flag in path_score.flags} for _, path_score in surviving]
        best_ids = flag_ids[0]
        others_union: set[object] = set().union(*flag_ids[1:]) if len(flag_ids) > 1 else set()

        # An alternative may claim "avoids N" only if it is actually safer. Route 1 of the
        # Dhanmondi->Gulshan pair is 2 minutes slower AND passes five flags against the
        # recommended route's three -- and it still avoids two the recommended one passes,
        # so the literal count is 2. Printing that alone would be true and misleading: it
        # sells a strictly worse route on the half of the comparison that flatters it.
        # A slower, less safe route gets the time difference and nothing else.
        best_safety = surviving[0][1].safety_score
        avoided_counts = [len(others_union - best_ids)] + [
            len(best_ids - ids) if path_score.safety_score > best_safety else 0
            for _, path_score in surviving[1:]
        ]

        responses: list[RouteResponse] = []
        for index, (route, path_score) in enumerate(surviving):
            responses.append(
                RouteResponse(
                    route_id=f"route_{route.engine}_{index}",
                    path=[
                        RouteSegment(latitude=lat, longitude=lon) for lat, lon in route.path
                    ],
                    distance_km=round(route.distance_m / 1000.0, 2),
                    duration_minutes=max(1, round(route.duration_s / 60.0)),
                    safety_score=path_score.safety_score,
                    composite_score=round(
                        composite(path_score.safety_score, route.duration_s, fastest_s), 1
                    ),
                    flags=[self._to_route_flag(flag) for flag in path_score.flags],
                    explanation=explain_route(
                        path_score.flags,
                        duration_s=route.duration_s,
                        fastest_duration_s=fastest_s,
                        avoided_count=avoided_counts[index],
                    ),
                    engine=route.engine,
                    filter_relaxed=filter_relaxed,
                    notes=notes,
                )
            )
        return responses


route_service = RouteService()
