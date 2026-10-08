"""
Validated LLM output shapes.

Every call through `app.llm.client` names one of these as its response format and
returns an instance of it, or raises. There is no path that hands raw model text
to the rest of the application — that is the "no LLM output reaches a user
unvalidated" invariant (IMPLEMENTATION_PLAN.md §4).

Keep these small. The models are free-tier and a wide schema is a wider target
for a refusal or a malformed field; `GeoGuess` below is four fields for exactly
that reason.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.risk import MobilityImpact


class GeoGuess(BaseModel):
    """
    The Geolocation Agent's LLM fallback, used only when the gazetteer misses.

    `resolved` is the field that matters. The invariant is "unresolvable
    locations are discarded, never guessed", and the only way a model can honour
    it is by being given somewhere to say no. Measured on 2026-10-07 against the
    six-case probe: `gemini-3.5-flash-lite` refused both fabricated places,
    `gemini-3.1-flash-lite` invented coordinates for one of them twice in a row
    at 0.95 confidence, which is why it is not in the chain.

    `confidence` is the model's own number and is **not** trusted on its own —
    the agent additionally rejects any point outside the pilot bounding box,
    because `openai/gpt-oss-120b` placed Sayedabad 12.6 km from where it is while
    reporting 0.78.
    """

    resolved: bool = Field(
        description=(
            "False if this is not a real, specific, identifiable place in Dhaka. "
            "Never guess — a wrong pin is worse than no pin."
        )
    )
    lat: float | None = Field(default=None, description="Latitude, or null when resolved is false.")
    lon: float | None = Field(default=None, description="Longitude, or null when resolved is false.")
    confidence: float = Field(ge=0.0, le=1.0, description="0 when resolved is false.")


NewsKind = Literal[
    "road_accident",
    "fire",
    "clash",
    "blockade",
    "procession",
    "waterlogging",
    "construction",
    "utility_outage",
    "other",
]
"""
`IncidentKind` minus `chronic`, which is a property of a place over months and not
something one news article can report. Offering it would invite the model to file
"this road is often bad" as an incident.
"""


class NewsIncident(BaseModel):
    """
    One mobility-affecting event the Live Risk Agent read out of an article. D04.

    Deliberately smaller than `ExtractedIncident`: the agent adds the source, the
    document and the timestamps itself rather than asking a model to copy them.
    There is no `occurred_at` — free-tier models are poor at turning "গতকাল
    সন্ধ্যায়" into an instant, and the article's own publication time is a better
    anchor than a guessed one.
    """

    kind: NewsKind
    location_text: str = Field(
        description=(
            "The most specific place name, copied from the article in its own "
            "script, without surrounding words such as রাজধানীর or এলাকায়."
        )
    )
    mobility_impact: MobilityImpact
    severity_hint: Literal["low", "medium", "high"] | None = None
    summary_en: str = Field(description="One short English sentence, for the audit trail.")
    confidence: float = Field(ge=0.0, le=1.0)


class NewsExtraction(BaseModel):
    """
    Everything one article reports that affects movement in Dhaka. Usually empty.

    An empty list is the expected answer for most articles, and the prompt says so:
    a model told that silence is normal is far less likely to invent an incident to
    have something to return.
    """

    incidents: list[NewsIncident] = Field(default_factory=list, max_length=3)
