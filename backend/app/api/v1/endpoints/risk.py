"""
Risk surface endpoints.

    GET /api/v1/risk/flags?bbox=<west,south,east,north>&as_of=<iso8601>

The map's only source of risk flags. The client does not read `risk_flags` through
Supabase — the table has RLS on with no policies, deliberately — because decay,
time-of-day modulation (D02) and the forward-looking view (D09) are arithmetic
that must have exactly one implementation, and a mobile client is not the place
for it.

`as_of` already works, and does more than it was planned to. Because every flag's
`expires_at` is derived and stored, evaluating the surface at a future instant
makes short-lived flags **drop out of the response**: measured against the D01
fixture, 20 flags now, 16 in six hours, 10 in twelve, 4 in two days. So the
"no stale red zones" claim is demonstrable from D01 rather than D02.

`as_of` now also changes what the flags *say*. Every response carries
`severity_now` alongside `severity_0`: the stored severity decayed to the instant
asked about, with the hour-of-day multiplier applied
(`app/scoring/decay.py`). So dragging the time control forward makes flags fade
before they vanish, which is demo beat 5. D09 reuses the same parameter to look
forward past `valid_from`.

`severity_0` stays in the response and never changes. The detail sheet shows both,
because "74 at 14:31, 42 now" is the provenance claim; a single number cannot say
that the flag is decaying rather than simply being moderate.

**A note for anyone testing with curl:** pass the instant with a `Z` suffix, not
`+00:00`. A literal `+` in a query string decodes to a space, the value fails to
parse, and the request 422s for a reason that has nothing to do with the date.
Browsers and `Date.toISOString()` produce `Z`, so clients are unaffected.
"""

from datetime import UTC, datetime
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.community import CommunityCluster
from app.contracts.news_crime import NewsCrimeIncident
from app.contracts.risk import RiskFlag
from app.contracts.surface import RiskSurface
from app.core.config import settings
from app.core.database import get_db
from app.scoring.clusters import DbClusterSurface
from app.scoring.factory import get_risk_surface
from app.scoring.news_crime import DbNewsCrimeSurface

router = APIRouter()

MAX_BBOX_SPAN_DEGREES: Final[float] = 2.0
"""
The widest box a single request may ask for, in degrees.

About 220 km, which comfortably covers Dhaka and its approaches. The limit is
there because a client bug that asks for the whole country would otherwise return
`MAX_FLAGS_PER_READ` arbitrary flags and look like a data problem rather than a
request problem.
"""


class CommunityClustersResponse(BaseModel):
    """
    Envelope for a bounding-box read of `community_clusters`.

    Same shape as `RiskFlagsResponse` and a separate response on a separate route,
    rather than a second array inside that one. Two reasons, and the first is the
    one that matters:

    1. **They are different claims.** A flag is a published mobility claim derived
       from edited sources; a cluster is a count of what strangers reported. Serving
       them in one envelope is the first step toward a client that treats them as
       interchangeable, which is the confusion Defect 54 logs about the map drawing
       both as the same pin.
    2. A client that wants only one does not pay for the other, and the map fetches
       both in parallel anyway.
    """

    as_of: datetime
    count: int = Field(ge=0)
    clusters: list[CommunityCluster]


class NewsCrimeResponse(BaseModel):
    """
    Envelope for a bounding-box read of `news_crime_incidents`.

    A third route rather than a third array, for the reason above applied once
    more. These three surfaces answer three different questions — *is this road
    passable*, *are people reporting things here*, *did a newspaper report a crime
    here* — and they have three different reliability models. The moment they share
    an envelope, a client starts treating them as one list.
    """

    as_of: datetime
    count: int = Field(ge=0)
    incidents: list[NewsCrimeIncident]


class RiskFlagsResponse(BaseModel):
    """
    Envelope for a bounding-box read.

    `as_of` is echoed deliberately: when D02's time control is dragged, the client
    needs to be able to tell which instant the pins it is drawing belong to, and a
    bare array cannot say that.
    """

    as_of: datetime
    count: int = Field(ge=0)
    flags: list[RiskFlag]


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    """
    `west,south,east,north` to `(min_lat, min_lon, max_lat, max_lon)`.

    **The wire order is lon-first**, because that is what every mapping tool,
    GeoJSON and PostGIS itself use, and a client assembling a bbox will have taken
    it from one of those. The return order is lat-first, because that is how the
    rest of this codebase talks. The swap happens here, once, rather than being
    rediscovered at each call site.
    """
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "bbox needs four comma-separated numbers: west,south,east,north "
                "(min_lon,min_lat,max_lon,max_lat)"
            ),
        )

    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"bbox values must be numbers, got {raw!r}",
        ) from None

    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox longitudes must be between -180 and 180",
        )
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox latitudes must be between -90 and 90",
        )
    if west >= east or south >= north:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bbox must be west<east and south<north",
        )
    if (east - west) > MAX_BBOX_SPAN_DEGREES or (north - south) > MAX_BBOX_SPAN_DEGREES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"bbox is larger than {MAX_BBOX_SPAN_DEGREES} degrees on a side; "
                "ask for a smaller area"
            ),
        )

    return south, west, north, east


def _resolve_as_of(as_of: datetime | None) -> datetime:
    """
    The instant to evaluate the surface at.

    A naive value is read as UTC rather than rejected: clients serialise dates in
    a dozen ways and a 422 on a missing `Z` would be a poor trade. The flags are
    stored as `timestamptz` and compared against this instant in SQL, so it has to
    be aware by the time it reaches the surface — and the edge of the system is
    where that conversion belongs.
    """
    if as_of is None:
        return datetime.now(UTC)
    if as_of.tzinfo is None:
        return as_of.replace(tzinfo=UTC)
    return as_of


@router.get(
    "/flags",
    response_model=RiskFlagsResponse,
    summary="Risk flags inside a bounding box",
)
async def get_risk_flags(
    bbox: Annotated[
        str,
        Query(
            description="west,south,east,north — e.g. 90.30,23.66,90.54,23.94",
            examples=["90.30,23.66,90.54,23.94"],
        ),
    ],
    as_of: Annotated[
        datetime | None,
        Query(
            description=(
                "ISO 8601 instant to evaluate the surface at; defaults to now. "
                "Use a Z suffix rather than +00:00 — a literal + in a query string "
                "decodes to a space."
            ),
            examples=["2026-10-07T18:00:00Z"],
        ),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> RiskFlagsResponse:
    """
    Live risk flags in an area, in the `RiskFlag` contract shape.

    Unauthenticated, matching `/crimes/nearby` and `/crimes/heatmap`. Nothing in
    `risk_flags` is user data — every flag is derived from published news or from
    public statistics — and the map is the one screen that must render before
    anything else has loaded.

    Read through a `RiskSurface`, never by querying the table here. Which
    implementation answers is `RISK_SURFACE_IMPL` — `db` or `seeded` — and this
    function cannot tell the difference, because `surface` is typed as the protocol
    rather than the class. That is what makes the offline demo path an environment
    variable instead of a branch.
    """
    min_lat, min_lon, max_lat, max_lon = _parse_bbox(bbox)
    at = _resolve_as_of(as_of)

    surface: RiskSurface = get_risk_surface(db)
    flags = await surface.flags_in_bbox(min_lat, min_lon, max_lat, max_lon, at)

    return RiskFlagsResponse(as_of=at, count=len(flags), flags=flags)


@router.get(
    "/clusters",
    response_model=CommunityClustersResponse,
    summary="Corroborated community report clusters inside a bounding box",
)
async def get_community_clusters(
    bbox: Annotated[
        str,
        Query(
            description="west,south,east,north - e.g. 90.30,23.66,90.54,23.94",
            examples=["90.30,23.66,90.54,23.94"],
        ),
    ],
    as_of: Annotated[
        datetime | None,
        Query(
            description=(
                "ISO 8601 instant to evaluate the clusters at; defaults to now. "
                "Use a Z suffix rather than +00:00."
            ),
            examples=["2026-10-13T18:00:00Z"],
        ),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> CommunityClustersResponse:
    """
    Live community clusters in an area: where several people independently reported
    something, as a count and a recency.

    **A single report is never here.** The database will not store a cluster with
    fewer than two independent reporters
    (`community_clusters_needs_two_reporters`), and reports themselves are private
    to their author -- `crime_reports` is readable only by the user who filed each
    row. See `app/policy/community.py` for the thresholds and the reasoning.

    Unauthenticated, matching `/risk/flags`. Nothing served here is user data: a
    cluster carries counts, a radius and two timestamps. It has no field for a
    narrative, a category or a report id, and the surface does not select those
    columns -- so this endpoint cannot leak a report even if a later caller asks it
    to.

    `as_of` behaves exactly as it does for flags, and for the same reason: dragging
    the time control forward decays a cluster's `severity_now` and drops it from the
    response once it is past `expires_at`. A cluster is the object most at risk of
    becoming a permanent label on a street, so being able to demonstrate that it
    fades is the point rather than a nicety.

    Returns an empty list under `RISK_SURFACE_IMPL=seeded`. There is deliberately no
    cluster fixture: a fabricated cluster would be an invented claim that residents
    of Dhaka reported incidents at a named corner, which is a worse thing to put on
    a stage than an empty layer. See `app/scoring/clusters.py`.
    """
    min_lat, min_lon, max_lat, max_lon = _parse_bbox(bbox)
    at = _resolve_as_of(as_of)

    if settings.RISK_SURFACE_IMPL.strip().lower() != "db":
        return CommunityClustersResponse(as_of=at, count=0, clusters=[])

    surface = DbClusterSurface(db)
    clusters = await surface.clusters_in_bbox(min_lat, min_lon, max_lat, max_lon, at)

    return CommunityClustersResponse(as_of=at, count=len(clusters), clusters=clusters)


@router.get(
    "/news-crime",
    response_model=NewsCrimeResponse,
    summary="Crime reported by named news publishers inside a bounding box",
)
async def get_news_crime(
    bbox: Annotated[
        str,
        Query(
            description="west,south,east,north - e.g. 90.30,23.66,90.54,23.94",
            examples=["90.30,23.66,90.54,23.94"],
        ),
    ],
    as_of: Annotated[
        datetime | None,
        Query(
            description=(
                "ISO 8601 instant to evaluate the incidents at; defaults to now. "
                "Use a Z suffix rather than +00:00."
            ),
            examples=["2026-10-14T18:00:00Z"],
        ),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> NewsCrimeResponse:
    """
    Crime that a named news publisher reported at a place in Dhaka.

    **Every statement here names its source**, and that is what makes this surface
    admissible rather than a safety rating of a neighbourhood. *"Robbery reported by
    Prothom Alo, 2 days ago"* is a checkable fact about a published article; *"there
    was a robbery here"* is a claim this product has no standing to make, and
    *"this area is dangerous"* is the permanent area label the concept document
    rules out. The database enforces the first of those with a CHECK on the
    `statement` column, and `app/policy/attribution.py` is its only writer.

    `sources` carries the citations so the client can link out. A client must render
    `statement` as given and must **not** compose its own sentence from `category` —
    doing so drops the attribution, which is the entire basis for this surface
    using crime vocabulary at all.

    Unauthenticated, matching `/risk/flags` and `/risk/clusters`. Nothing here is
    user data: every row is derived from a published newspaper article, and the
    extraction schema has no field for a person's name — see
    `app/llm/models.py :: NewsCrime`.

    `as_of` behaves as it does everywhere else. These incidents decay on a five-day
    half-life (`policy/attribution.NEWS_CRIME_HALF_LIFE_HOURS`), so dragging the
    time control forward fades them and then drops them. That is deliberate and it
    is the answer to the obvious objection: a crime map that never forgets becomes a
    permanent judgement about a neighbourhood.

    Returns an empty list under `RISK_SURFACE_IMPL=seeded`. There is no fixture, for
    the same reason there is no cluster fixture — a fabricated citation would be a
    made-up claim attributed to a real newspaper, which is worse than an empty layer.
    """
    min_lat, min_lon, max_lat, max_lon = _parse_bbox(bbox)
    at = _resolve_as_of(as_of)

    if settings.RISK_SURFACE_IMPL.strip().lower() != "db":
        return NewsCrimeResponse(as_of=at, count=0, incidents=[])

    surface = DbNewsCrimeSurface(db)
    incidents = await surface.crimes_in_bbox(min_lat, min_lon, max_lat, max_lon, at)

    return NewsCrimeResponse(as_of=at, count=len(incidents), incidents=incidents)
