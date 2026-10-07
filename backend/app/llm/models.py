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

from pydantic import BaseModel, Field


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
