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

What `as_of` does **not** do yet is change `severity_0` in the response. A flag
still reports the severity it had when it was observed, so a fading flag does not
visibly fade before it disappears. That is D02's severity-on-read, and D09 reuses
the same parameter to look forward past `valid_from`.

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

from app.contracts.risk import RiskFlag
from app.contracts.surface import RiskSurface
from app.core.database import get_db
from app.scoring.surface_db import DbRiskSurface

router = APIRouter()

MAX_BBOX_SPAN_DEGREES: Final[float] = 2.0
"""
The widest box a single request may ask for, in degrees.

About 220 km, which comfortably covers Dhaka and its approaches. The limit is
there because a client bug that asks for the whole country would otherwise return
`MAX_FLAGS_PER_READ` arbitrary flags and look like a data problem rather than a
request problem.
"""


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
            description="west,south,east,north — e.g. 90.33,23.70,90.50,23.90",
            examples=["90.33,23.70,90.50,23.90"],
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

    Read through a `RiskSurface`, never by querying the table here. D02 adds
    `SeededRiskSurface` and a `RISK_SURFACE_IMPL` setting to choose between them;
    this line is the only one that changes, because `surface` is typed as the
    protocol rather than the class.
    """
    min_lat, min_lon, max_lat, max_lon = _parse_bbox(bbox)
    at = _resolve_as_of(as_of)

    surface: RiskSurface = DbRiskSurface(db)
    flags = await surface.flags_in_bbox(min_lat, min_lon, max_lat, max_lon, at)

    return RiskFlagsResponse(as_of=at, count=len(flags), flags=flags)
