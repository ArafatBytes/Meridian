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

from typing import Final

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.contracts.risk import GeoResolution
from app.geo.agent import MAX_QUERY_CHARS, resolve_place

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
