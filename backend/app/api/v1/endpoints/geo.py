"""
Place resolution endpoint.

    POST /api/v1/geo/resolve     {"text": "Mirpur 10 golchattar"}

Text in, coordinates plus `method` out. `method` is the part that matters and is
shown to the user on the map as a chip:

    gazetteer       matched our Dhaka gazetteer. The reliable path.
    llm_gazetteer   the gazetteer missed and a language model answered, inside
                    the pilot bounding box.
    unresolved      we do not know. **No pin is drawn.**

`unresolved` returns HTTP 200, not 404. It is a successful answer to the question
"where is this?" — the answer being "we will not guess" — and the client renders
it as an explicit "could not resolve that place" state rather than an error. That
is the "unresolvable locations are discarded, never guessed" invariant made
visible, and a better thing to show a judge than a silent failure.

No authentication, by design: this reads a public, static data file and, at worst,
spends one free-tier LLM request. It is rate-limited by the free tier itself.
"""

import logging
from typing import Any, Final

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.contracts.risk import GeoResolution
from app.geo import nominatim
from app.geo.agent import MAX_QUERY_CHARS, resolve_place

logger = logging.getLogger(__name__)

router = APIRouter()


class ResolveRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_QUERY_CHARS,
        description="A place reference, in Bangla script, romanised Bangla, or a mix.",
        examples=["Mirpur 10 golchattar", "মিরপুর ১০ গোলচত্বর", "Jatrabari chourasta"],
    )
    allow_llm: bool = Field(
        default=True,
        description=(
            "Set false to restrict resolution to the gazetteer, spending no LLM "
            "request. Ingestion uses this for bulk work."
        ),
    )


class ResolveResponse(BaseModel):
    """
    The resolution, plus the query it came from.

    `query` is echoed because the map's search box is asynchronous: a slow answer
    for an earlier query must not overwrite the display of a later one, and the
    client needs something to compare against.
    """

    query: str
    resolution: GeoResolution


EXAMPLE_UNRESOLVED: Final = "Nothing was matched; the client must not draw a pin."


@router.post(
    "/resolve",
    response_model=ResolveResponse,
    summary="Resolve a Dhaka place reference to coordinates",
    description=__doc__,
)
async def resolve(request: ResolveRequest) -> ResolveResponse:
    resolution = await resolve_place(request.text, allow_llm=request.allow_llm)
    return ResolveResponse(query=request.text, resolution=resolution)


# ---------------------------------------------------------------------------
# The Nominatim proxy — D06, defect 10
# ---------------------------------------------------------------------------
# Four screens were calling nominatim.openstreetmap.org straight from the device with
# React Native's default User-Agent and no caching. That violates Nominatim's usage
# policy, spends the per-IP rate limit separately on every phone, and is invisible to
# the server. These two endpoints put one identifying agent and one shared Redis cache
# in front of it.
#
# Deliberately NOT merged into /resolve. That endpoint is allowed to refuse — the
# "discarded, never guessed" invariant — and D03 found the hard way that a tier which
# answers everything will overturn a deliberate refusal if the two share a path. A
# general geocoder and a guarded one stay separate.


class NominatimPlace(BaseModel):
    """One candidate from OpenStreetMap. Not a `GeoResolution`: carries no judgement."""

    display_name: str | None
    lat: float
    lon: float
    type: str | None = None


class GeoSearchResponse(BaseModel):
    query: str
    results: list[NominatimPlace]


class GeoReverseResponse(BaseModel):
    lat: float
    lon: float
    display_name: str | None
    address: dict[str, Any] = Field(default_factory=dict)


@router.get(
    "/search",
    response_model=GeoSearchResponse,
    summary="Forward geocode through the server's Nominatim proxy",
)
async def geo_search(q: str = Query(min_length=1, max_length=200)) -> GeoSearchResponse:
    """
    Candidate places for a free-text query.

    Returns an **empty list** rather than an error when Nominatim is unreachable: the
    client's job here is to offer suggestions, and no suggestions is a usable state
    while a 502 is not.
    """
    try:
        results = await nominatim.search(q)
    except nominatim.NominatimUnavailable as exc:
        logger.warning("nominatim search failed for %r: %s", q, exc)
        results = []
    return GeoSearchResponse(query=q, results=[NominatimPlace(**r) for r in results])


@router.get(
    "/reverse",
    response_model=GeoReverseResponse,
    summary="Reverse geocode through the server's Nominatim proxy",
)
async def geo_reverse(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
) -> GeoReverseResponse:
    """
    An address for a coordinate, or a null `display_name` when there is not one.

    Same reasoning as `/search`: a missing address is a state the reporting screen can
    render ("drop a pin here anyway"), so it is not an error.
    """
    try:
        place = await nominatim.reverse(lat, lon)
    except nominatim.NominatimUnavailable as exc:
        logger.warning("nominatim reverse failed for %s,%s: %s", lat, lon, exc)
        place = None
    return GeoReverseResponse(
        lat=lat,
        lon=lon,
        display_name=place["display_name"] if place else None,
        address=place.get("address", {}) if place else {},
    )
