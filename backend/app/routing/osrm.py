"""
The OSRM client. Defect 7.

Three things were wrong with what this replaces, and they compound:

1. **It hardcoded `http://router.project-osrm.org`** — a public demo server run by
   someone else, rate-limited, with no uptime commitment. `OSRM_BASE_URL` existed in
   settings and nothing read it. The demo depended on a stranger's rate limiter.
2. **It threw away OSRM's `duration`** and computed `dist_km * 60 / 30` instead. A flat
   30 km/h across Dhaka is wrong in both directions — optimistic in Motijheel at 18:00,
   pessimistic on an empty flyover at 04:00 — and OSRM had already answered the question
   from the road graph.
3. **Driving only.** A pedestrian asking for a safe way home got car directions, which
   is the opposite of useful in a city where the safest route is often a walk.

---

## The fallback, and why it is loud

If the configured server cannot be reached we fall back to the public demo server, and
we say so — at `WARNING`, with the reason, on every request. The alternative designs are
both worse: failing hard turns one unreachable container into a dead demo, and falling
back silently means the first time anyone notices is when the demo server rate-limits in
front of an audience.

`DEMO_PLAN.md` D10's failure drills exercise this path deliberately, so it has to work
*and* has to be visible. `RouteResponse.engine` carries which one answered, so the
walkthrough can assert it rather than trusting the log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, Literal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "PUBLIC_DEMO_BASE_URL",
    "OsrmRoute",
    "OsrmUnavailable",
    "Profile",
    "fetch_routes",
    "fetch_routes_via",
]

Profile = Literal["driving", "foot"]
"""
The OSRM profiles this project asks for.

`driving` and `foot` only. OSRM's `bike` profile exists but the graph built in §9 is
`car.lua`, so asking for `bike` would silently be answered by the car graph — a wrong
answer that looks right, which is worse than no answer.

⚠️ **`foot` needs its own graph.** A `car.lua` graph will answer a `/foot/` request, and
it will route pedestrians down flyovers and the wrong way along one-way streets. See
`WALKING_GRAPH_CAVEAT` below; this is honest-but-incomplete, and it is written down
rather than hidden.
"""

PUBLIC_DEMO_BASE_URL: Final[str] = "http://router.project-osrm.org"
"""The server defect 7 is about. Kept only as the loud fallback."""

WALKING_GRAPH_CAVEAT: Final[str] = (
    "The local OSRM graph is built from car.lua (DEMO_PLAN.md section 9 step 5). It will "
    "answer a /foot/ request, but with car turn restrictions -- so a walking route may "
    "use a flyover or obey a one-way street that a pedestrian would not. Building a "
    "second graph with foot.lua is the fix; it is not demo-critical and is not in D06."
)

_TIMEOUT_SECONDS: Final[float] = 8.0
"""
Up from the previous 5 s.

A local OSRM answers a Dhaka crossing in tens of milliseconds, so this budget is not for
the local server -- it is for the demo-server fallback over a venue network, where 5 s was
tight enough to turn a working fallback into a failure.
"""


class OsrmUnavailable(RuntimeError):
    """Neither the configured server nor the fallback answered."""


@dataclass(frozen=True)
class OsrmRoute:
    """
    One route as OSRM returned it, before anything scores it.

    `duration_s` is **OSRM's own number**, from the road graph — not distance divided by
    an assumed speed. That is half of defect 7.
    """

    path: list[tuple[float, float]]  # (lat, lon), travel order
    distance_m: float
    duration_s: float
    engine: str  # "local" | "public-demo", for the response and the walkthrough


def _base_url() -> tuple[str, bool]:
    """
    The configured base URL, and whether it is the public demo server.

    An empty or whitespace `OSRM_BASE_URL` counts as unset and resolves to the demo
    server, because a half-configured value failing silently is how defect 7 survived
    this long.
    """
    configured = (settings.OSRM_BASE_URL or "").strip().rstrip("/")
    if not configured:
        return PUBLIC_DEMO_BASE_URL, True
    return configured, configured.rstrip("/") == PUBLIC_DEMO_BASE_URL


def _parse(payload: dict[str, Any], engine: str) -> list[OsrmRoute]:
    """OSRM's response into `OsrmRoute`s, skipping anything malformed."""
    if payload.get("code") != "Ok":
        return []

    routes: list[OsrmRoute] = []
    for raw in payload.get("routes", []):
        coordinates = (raw.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        # OSRM speaks (lon, lat). Everything above this line speaks (lat, lon), and the
        # conversion happens exactly here so nothing downstream has to remember.
        path = [(float(c[1]), float(c[0])) for c in coordinates]
        routes.append(
            OsrmRoute(
                path=path,
                distance_m=float(raw.get("distance", 0.0)),
                duration_s=float(raw.get("duration", 0.0)),
                engine=engine,
            )
        )
    return routes


async def _request(base_url: str, profile: Profile, coords: str, engine: str) -> list[OsrmRoute]:
    url = f"{base_url}/route/v1/{profile}/{coords}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
                # OSRM returns alternatives only when it finds genuinely distinct ones,
                # so asking for 3 does not guarantee 3 -- and a corridor with one sane
                # road through it *should* return one route rather than two near-copies.
                "alternatives": "3",
            },
        )
    response.raise_for_status()
    return _parse(response.json(), engine)


async def fetch_routes_via(
    *,
    start: tuple[float, float],
    waypoints: list[tuple[float, float]],
    end: tuple[float, float],
    profile: Profile = "driving",
) -> list[OsrmRoute]:
    """
    A route forced through intermediate waypoints. `app/routing/alternatives.py` uses it.

    OSRM returns exactly one route when given a via-point -- alternatives and waypoints are
    mutually exclusive in its API -- which is fine, because the caller already knows which
    single detour it asked for and verifies the answer.

    No fallback to the demo server here, deliberately. This is a best-effort *extra*
    alternative; if the configured engine cannot answer it, the primary route is already in
    hand and spending a third party's rate limit on a bonus is the wrong trade.
    """
    points = [start, *waypoints, end]
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    base_url, is_demo = _base_url()
    return await _request_via(base_url, profile, coords, "public-demo" if is_demo else "local")


async def _request_via(
    base_url: str, profile: Profile, coords: str, engine: str
) -> list[OsrmRoute]:
    url = f"{base_url}/route/v1/{profile}/{coords}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
        )
    response.raise_for_status()
    return _parse(response.json(), engine)


async def fetch_routes(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    profile: Profile = "driving",
) -> list[OsrmRoute]:
    """
    Routes from `start` to `end`, from the configured OSRM, with a loud fallback.

    Both points are `(lat, lon)`. Raises `OsrmUnavailable` only when **both** the
    configured server and the public demo server fail — the caller's own fallback (a
    straight-line estimate) is then the last resort, and it is marked as such in the
    response so nobody mistakes it for a real route.
    """
    coords = f"{start[1]},{start[0]};{end[1]},{end[0]}"
    base_url, is_demo = _base_url()

    if is_demo:
        logger.warning(
            "OSRM_BASE_URL is unset or points at the public demo server (%s). Routing is "
            "running on someone else's rate limiter -- this is defect 7. Build the local "
            "graph (DEMO_PLAN.md section 9 item 2) and set OSRM_BASE_URL=http://osrm:5000.",
            PUBLIC_DEMO_BASE_URL,
        )
    if profile == "foot":
        logger.warning("walking route requested: %s", WALKING_GRAPH_CAVEAT)

    try:
        routes = await _request(base_url, profile, coords, "public-demo" if is_demo else "local")
        if routes:
            return routes
        logger.warning("OSRM at %s returned no usable route for %s", base_url, coords)
    except Exception as exc:
        logger.warning(
            "OSRM at %s failed (%s: %s)", base_url, type(exc).__name__, exc
        )

    if is_demo:
        raise OsrmUnavailable(f"OSRM at {base_url} returned nothing usable")

    # Configured server failed and it was not the demo server. Fall back, loudly.
    logger.warning(
        "FALLING BACK to the public OSRM demo server because %s did not answer. Routes "
        "will still be returned, but on a rate-limited third-party service -- fix the "
        "local container before relying on this.",
        base_url,
    )
    try:
        routes = await _request(PUBLIC_DEMO_BASE_URL, profile, coords, "public-demo")
    except Exception as exc:
        raise OsrmUnavailable(
            f"both {base_url} and {PUBLIC_DEMO_BASE_URL} failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not routes:
        raise OsrmUnavailable("neither the configured OSRM nor the demo server had a route")
    return routes
