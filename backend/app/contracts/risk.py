"""
Risk contracts — IMPLEMENTATION_PLAN.md §6.1.

The lifecycle these shapes describe, end to end:

    RawDocument          a fetched article                    (ingestion, D04)
      -> ExtractedIncident   what an LLM read out of it        (D04)
      -> GeoResolution       where "Mirpur 10 golchattar" is   (D03)
      -> RiskFlag            the thing a user finally sees      (D01 onward)

`RiskFlag` is the only one of these the client ever sees, and it is mirrored in
`frontend/src/types/contracts/risk.ts`.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FlagStatus = Literal["unconfirmed", "confirmed", "expired", "rejected"]
"""
Lifecycle of a flag.

`confirmed` is reachable only through Rumour Guard (D05) with two or more
independent sources. That is the "verification before publication" invariant,
and it is checked in three places: here, in
`tests/invariants/test_single_source_never_confirmed.py`, and by a CHECK
constraint on `risk_flags`.

`unconfirmed` is **published, not suppressed** — at reduced weight, and visibly
distinct on the map. Suppressing it would throw away the early signal that is
half the point of reading news at all; promoting it silently would break the
invariant. See `app.policy.independence.confidence`.
"""


class IncidentKind(StrEnum):
    """What happened. Decides the default half-life and radius (D02)."""

    ROAD_ACCIDENT = "road_accident"
    FIRE = "fire"
    CLASH = "clash"
    BLOCKADE = "blockade"
    PROCESSION = "procession"
    WATERLOGGING = "waterlogging"
    CONSTRUCTION = "construction"
    UTILITY_OUTAGE = "utility_outage"
    CHRONIC = "chronic"  # from archive mining or police statistics; long half-life
    OTHER = "other"


class MobilityImpact(StrEnum):
    """
    The only vocabulary allowed to describe effect. Concept document §9.

    Deliberately short, and deliberately about *movement*. There is no value
    here for "dangerous", "unsafe", "riot" or any characterisation of the people
    involved, because the product does not make that claim. A procession is a
    road that is blocked.
    """

    ROAD_BLOCKED = "road_blocked"
    HEAVY_CROWD = "heavy_crowd"
    DELAY_LIKELY = "delay_likely"
    LANE_CLOSED = "lane_closed"
    IMPASSABLE = "impassable"
    NONE = "none"


class SourceRef(BaseModel):
    """One publisher's account of an event. Frozen: provenance is not editable."""

    model_config = ConfigDict(frozen=True)

    source_id: str  # stable publisher id, e.g. "prothom_alo"
    url: str
    published_at: datetime | None
    title: str | None = None
    snippet: str | None = None


class RawDocument(BaseModel):
    """A fetched article, stored before anything interprets it. D04."""

    doc_id: str  # sha256 of the canonical URL
    source_id: str
    url: str
    fetched_at: datetime
    published_at: datetime | None
    language: Literal["bn", "en", "mixed"]
    title: str
    body: str
    raw_ref: str | None = None  # object-store key; never inline HTML


class ExtractedIncident(BaseModel):
    """Output of one LLM extraction pass over one RawDocument. D04."""

    kind: IncidentKind
    summary_en: str
    summary_bn: str | None = None
    location_text: str  # colloquial, exactly as the article wrote it
    occurred_at: datetime | None
    severity_hint: Literal["low", "medium", "high"] | None = None
    mobility_impact: MobilityImpact
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    source: SourceRef


class GeoResolution(BaseModel):
    """
    Where a colloquial place name actually is. D03.

    `method` carries how we know. `unresolved` means the incident is dropped —
    see the "unresolvable locations are discarded, never guessed" invariant. A
    wrong pin is worse than no pin.
    """

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0, le=20_000)
    resolved_name: str
    method: Literal["gazetteer", "llm_gazetteer", "nominatim", "unresolved"]
    confidence: float = Field(ge=0.0, le=1.0)
    admin_area: str | None = None


class TimeProfile(BaseModel):
    """Hour-of-day multipliers, 24 entries, 1.0 = neutral. Concept document §5.6."""

    multipliers: list[float] = Field(min_length=24, max_length=24)


class RiskFlag(BaseModel):
    """
    A single, decaying, located claim about mobility. The only risk object the
    client sees.

    Four fields carry invariants rather than data:

    * `half_life_hours` — mandatory and positive. There are no permanent area
      labels in this product. The database carries the same CHECK.
    * `severity_now` — **computed on read, never stored.** `severity_0` is the
      severity at `observed_at` and never changes; this is that value decayed to
      the instant the caller asked about, with the hour-of-day multiplier applied
      (`app.scoring.decay.severity_at`). It is a required field rather than an
      optional one because a surface that forgot to compute it would otherwise
      serve a flag that silently never fades, and the map colours pins by this
      value. There is no setter: the two `RiskSurface` implementations are the only
      producers.
    * `expires_at` — **derived** from `observed_at`, `severity_0`,
      `half_life_hours` and `valid_to` by a database trigger
      (`trg_risk_flags_expires_at`), which discards whatever a caller supplied.
      There is deliberately no Python implementation of that formula: one rule, one
      place. Never hand-set, never accepted from a client, never in a fixture.
    * `mobility_statement` — **only** written by
      `app.policy.framing.to_mobility_statement`. Nothing else may produce this
      string, including a fixture file.
    """

    flag_id: UUID
    event_key: str  # dedup identity, assigned by Rumour Guard (D05)
    kind: IncidentKind
    status: FlagStatus
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0)
    severity_0: float = Field(ge=0.0, le=100.0)  # severity at observed_at
    severity_now: float = Field(ge=0.0, le=100.0)
    half_life_hours: float = Field(gt=0)  # §4: decay is mandatory
    observed_at: datetime
    expires_at: datetime  # derived, never hand-set
    source_count: int = Field(ge=1)
    sources: list[SourceRef] = Field(default_factory=list)
    mobility_statement: str  # ONLY written by policy.framing
    time_profile: TimeProfile | None = None

    # ---------------------------------------------------------------- D05 ----
    # When the second independent publisher arrived and `status` became
    # `confirmed`. Null on an unconfirmed flag, which is most of them, and null on
    # a fixture flag that was simply authored confirmed.
    #
    # This is a *claim about our own process*, not about the event: it answers
    # "when did you decide to believe this?", which is the question behind demo
    # beat 2's "confirmed 14:31". Set only by Rumour Guard.
    confirmed_at: datetime | None = None

    # How much of this flag's severity should count in a decision, 0-1.
    #
    # **Derived from `status`, never stored**, by `policy.independence.confidence`.
    # The two `RiskSurface` implementations are its only producers, exactly as with
    # `severity_now`.
    #
    # It exists as a field rather than being left for each consumer to re-derive
    # because "unconfirmed is published at reduced weight" (plan S15) is a policy
    # decision, and a policy decision duplicated in the routing service and again
    # in TypeScript is a policy decision that will come to mean three things.
    # `severity_now` is deliberately **not** damped by it: that value is the decay
    # story the flag sheet narrates ("74 when observed, 31 now, 42% remaining"),
    # and multiplying it would make that arithmetic lie. Consumers that are making
    # a decision want `severity_now * confidence`; see
    # `app.scoring.decay.effective_severity`.
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # ---------------------------------------------------------------- D09 ----
    # Forward-dated flags: an announced procession is a claim about a window in
    # the future, not about now. Both nullable, because a flag read out of the
    # news is about the present and has neither.
    #
    # These two columns exist from D01 even though the Scheduled Risk Agent is
    # D09, because adding them later would mean a migration *and* a contract
    # change *and* a TypeScript mirror update on D09's single day. They cost
    # nothing now.
    valid_from: datetime | None = None
    valid_to: datetime | None = None
