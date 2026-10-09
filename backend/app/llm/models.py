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


Cue = Literal["yes", "no", "unclear"]
"""
Three answers, not two. `unclear` is what a model reaches for instead of guessing,
and without it the only way to express doubt is to pick a side — the same reason
`GeoGuess.resolved` exists.
"""


class CrimeCues(BaseModel):
    """
    What is visibly present in one report photo. D07, ADR 0006.

    **The model never names a crime.** It answers five questions about physical
    cues; `app/vision/mapping.py` turns those into a candidate category, and the
    reporter confirms it. Three reasons that split is the whole design:

    * A photo cannot establish a crime — not intent, not consent, not who started
      it, not whether it is a film shoot. A model asked "is this a crime?" answers
      anyway. One asked "are two people in forceful contact?" can be checked.
    * Cues generalise where categories do not. "Physical confrontation" is shared
      by assault and robbery, so a photo of an unfamiliar crime still produces
      usable signal. ASK-HINT (WACV 2026) measures **over 20 AUC points** on
      UCF-Crime from this choice alone, same model, no training.
    * A model that hallucinates produces a wrong *cue*, which our mapping can
      refuse, rather than a wrong accusation already written on the screen.

    Field order matters: the cues come before `description` so the model commits
    to each yes/no/unclear before it starts writing prose that might talk it into
    a different answer.

    **Seven cues, not five.** The first five missed three of the four scenes in
    the 2026-10-09 test set, and the models were not at fault — they described a
    car fuel cap being forced, goods going into a bag, and two people pulling one
    bag, all accurately. There was simply no cue for any of them. That is the
    same failure as the COCO vocabulary gap this design replaced: a question that
    is never asked can never be answered. `struggle_over_property` and
    `goods_concealed` are new; `forced_entry` was widened past building openings.
    """

    physical_confrontation: Cue = Field(
        description="Two or more people in forceful physical contact. Standing close, arguing or gesturing is NOT this."
    )
    weapon_visible: Cue = Field(
        description="A gun, knife, stick or similar, held or aimed as a weapon. A tool merely being carried is 'no'."
    )
    property_damage: Cue = Field(
        description="Property that is broken, burnt, or defaced — not merely old, dirty or worn."
    )
    forced_entry: Cue = Field(
        description=(
            "A lock, door, window, gate, shutter, or a vehicle being forced, prised, "
            "picked or worked open — including hands or a tool at a lock, handle or "
            "fuel cap. Simply opening something normally is 'no'."
        )
    )
    unwanted_pursuit: Cue = Field(
        description="One person following, cornering or blocking another who is trying to get away."
    )
    struggle_over_property: Cue = Field(
        description=(
            "Two or more people pulling, grabbing or holding the same bag, phone or "
            "object at once. They need not be touching each other."
        )
    )
    goods_concealed: Cue = Field(
        description=(
            "Someone putting goods into a bag, pocket or clothing in a shop, stall or "
            "market. Holding or carrying an item openly is 'no'."
        )
    )
    people_count: int = Field(ge=0, le=50, description="People visible. 0 if none.")
    scene: Literal["street", "indoor", "vehicle", "other"]
    description: str = Field(
        max_length=200,
        description=(
            "ONE plain sentence of what is visibly happening. Describe only what "
            "can be seen. Do not name a crime, assign blame, or say what someone intends."
        ),
    )
