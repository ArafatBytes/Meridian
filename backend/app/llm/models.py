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


NewsCrimeCategory = Literal[
    "theft",
    "assault",
    "harassment",
    "vandalism",
    "burglary",
    "robbery",
    "fraud",
    "other",
]
"""
`crime_reports.category` verbatim — the same eight values a user picks from when
filing their own report, and the same eight the frontend colours markers by.

Deliberately not a wider or more precise taxonomy. The model is choosing a bucket
for a published article, and every value it can return has to be one the database
CHECK accepts, the frontend has a colour for, and
`app/policy/attribution.py::CATEGORY_NOUNS` has a noun for. A ninth value invented
here would fail at insert, which is the right failure but an avoidable one.
"""


class NewsCrime(BaseModel):
    """
    One crime an article reports as having happened at a place in Dhaka. D04 / S30.

    The sibling of `NewsIncident`, and the differences are the policy:

    * **No `mobility_impact`.** A robbery is not a road condition. The whole reason
      this is a separate object, a separate table and a separate policy module is
      that the mobility vocabulary cannot describe it — see the header of
      `migrations/versions/20261014120000__news_crime_incidents.sql`.
    * **No free-text summary reaches the user.** `summary_en` goes to
      `extracted_incidents` for the audit trail exactly as it does for mobility,
      and the published sentence is built by
      `app/policy/attribution.py::to_attributed_statement` from the category, the
      publisher and the date. The model never writes a map pin.
    * **No `occurred_at`.** Same reason as `NewsIncident`: free-tier models are
      poor at turning "গতকাল সন্ধ্যায়" into an instant, and the article's own
      publication time is a better anchor than a guessed one.
    * **No names.** There is nowhere in this schema to put a suspect, a victim or
      an officer, which is the cheapest possible way to guarantee none is
      published. A crime article is full of them.
    """

    category: NewsCrimeCategory
    location_text: str = Field(
        description=(
            "The most specific place name, copied from the article in its own "
            "script, without surrounding words such as রাজধানীর or এলাকায়."
        )
    )
    summary_en: str = Field(description="One short English sentence, for the audit trail.")
    confidence: float = Field(ge=0.0, le=1.0)


class NewsExtraction(BaseModel):
    """
    Everything one article reports that Meridian publishes. Usually empty.

    An empty list is the expected answer for most articles, and the prompt says so:
    a model told that silence is normal is far less likely to invent an incident to
    have something to return.

    **Two lists, one model call**, and that is a cost decision with a correctness
    consequence worth stating. The free tier is a few hundred requests a day and
    `MAX_EXTRACTIONS_PER_RUN` exists because of it, so asking the same article
    twice — once for movement, once for crime — would halve the throughput of
    both. One call reads the article once and sorts what it finds into the two
    vocabularies that are allowed to exist.

    The lists do **not** mix downstream. `incidents` goes to `risk_flags` through
    `policy/framing.py`; `crimes` goes to `news_crime_incidents` through
    `policy/attribution.py`. They share a model call and nothing else: separate
    tables, separate guards, separate decay, separate API. The coupling is where
    the money is and nowhere else.
    """

    incidents: list[NewsIncident] = Field(default_factory=list, max_length=3)
    crimes: list[NewsCrime] = Field(default_factory=list, max_length=3)


# ---------------------------------------------------------------------------
# D09 — the Scheduled Risk Agent
# ---------------------------------------------------------------------------

ScheduledDay = Literal["today", "tomorrow", "day_after"]
"""
Which day, relative to the article's own publication date.

**Not a date, and not a timestamp.** A free-tier model asked for
`2026-10-11T10:00:00+06:00` gets it wrong in ways that are expensive and quiet: a
shifted year, a dropped timezone, a plausible-looking instant that is a day out.
D08 measured the same class of failure on a 15-digit IMEI — three corruptions in
five attempts, and no amount of prompting fixed it. The lesson transfers: ask for
small enumerations and small integers, and do the arithmetic in code.

The article says "আগামীকাল সকাল ১০টা". A three-way choice plus an hour is exactly
that sentence, and `scheduled_risk._window()` turns it into a UTC instant from the
publication date, which we already know for certain.
"""


class ScheduledEvent(BaseModel):
    """
    One announced, not-yet-happened event that will affect movement. D09.

    The complement of `NewsIncident`, whose prompt explicitly discards
    "statements and announcements" — the thing this one is looking for.
    """

    kind: NewsKind
    location_text: str = Field(
        description=(
            "The most specific place name, copied from the article in its own "
            "script, without surrounding words such as রাজধানীর or এলাকায়."
        )
    )
    mobility_impact: MobilityImpact
    day: ScheduledDay = Field(
        description="Which day the article says it happens, relative to the article."
    )
    start_hour: int = Field(
        ge=0, le=23, description="Hour it starts, 0-23, Bangladesh local time."
    )
    end_hour: int | None = Field(
        default=None,
        ge=0,
        le=23,
        description="Hour it ends, if the article says. Null if it does not.",
    )
    severity_hint: Literal["low", "medium", "high"] | None = None
    summary_en: str = Field(description="One short English sentence, for the audit trail.")
    confidence: float = Field(ge=0.0, le=1.0)


class ScheduledExtraction(BaseModel):
    """
    Every future mobility event one article announces. Usually empty.

    Same `max_length=3` and same default-empty reasoning as `NewsExtraction`: most
    articles announce nothing, and a model told that silence is the normal answer
    invents far less.
    """

    events: list[ScheduledEvent] = Field(default_factory=list, max_length=3)


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


class GdDraft(BaseModel):
    """
    D08's one call: the body of a General Diary application. ADR 0007.

    Three fields, and the smallest of the three is the one that matters. The
    DMP form is a frame around a single blank space, and the Online GD app's
    `onnanno abedon` path is two fields -- the type, and one description box.
    Both want the same paragraph, so we generate it once.

    `narrative_bn` is the whole product. There is no second artefact to fall
    back on if it reads wrong, which is why a native speaker signing off is a
    gate on D08 and not a nicety.
    """

    # `max_length` is a real constraint on this field and also a ceiling on
    # where this model can run. Ollama compiles a strict `json_schema` into a
    # GBNF grammar, and a large `maxLength` blows that compiler up:
    # `failed to parse grammar`, before a single token is generated. Measured
    # 2026-10-10 against qwen3-vl:4b — 200, 500, 1000 and 1500 compile; 2000 and
    # 3000 do not. D07's `CrimeCues.description` is 200, which is why that tier
    # has never hit this.
    #
    # It does not bite today, because `LLM_CHAIN_GD` is cloud-only by decision.
    # It would bite the moment someone adds a local tier here, so: anything
    # above ~1500 needs this field relaxed for that provider, not a debugging
    # session.
    narrative_bn: str = Field(
        max_length=3000,
        description=(
            "The complainant's account in the formal written Bangla used in "
            "official applications, in the first person, beginning with "
            "'binito nibedon ei je,'. Only facts the complainant gave. Where a "
            "fact a duty officer would ask for is missing, write a bracketed gap "
            "rather than inventing one."
        ),
    )
    summary_en: str = Field(
        max_length=400,
        description=(
            "One sentence in English saying what the narrative claims happened, "
            "so the draft can be checked by someone who does not read Bangla "
            "before they sign it."
        ),
    )
    missing_details: list[str] = Field(
        description=(
            "Facts a duty officer will ask for that the complainant did not "
            "provide, in English, at most six. Empty when nothing is missing."
        ),
    )
