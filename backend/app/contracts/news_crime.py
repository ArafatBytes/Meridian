"""
The news-crime contract — what a published, attributed crime report looks like on
the wire.

Mirror: `frontend/src/types/contracts/newsCrime.ts`
Storage: `migrations/versions/20261014120000__news_crime_incidents.sql`
Policy:  `app/policy/attribution.py`

Three publishing surfaces now, and the differences between their contracts are the
clearest statement of what each one is allowed to claim:

    RiskFlag          kind + mobility_statement + sources   the product's own
                                                            claim about movement
    CommunityCluster  counts + statement, NO category       several users agreeing
    NewsCrimeIncident category + statement + sources        one named outlet said so

Note what this one has that `CommunityCluster` deliberately lacks — a **category**
and **sources** — and why that is not a relaxation of the rule but the same rule
applied to a different object.

A cluster withholds the category because its trustworthiness comes from *agreement
between anonymous accounts*, and attaching "robbery" to an anonymous aggregate
would be the product asserting what kind of place somewhere is. A news incident
carries the category precisely because it carries the **attribution**: the
sentence names the masthead that published it and the client gets the URL, so the
reader can check it. Take the attribution away and this would be the less
defensible of the two; with it, it is the more.

`sources` is the same `SourceRef` list `RiskFlag` uses, for the same reason: it is
the provenance, and provenance is what this surface is made of.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.risk import SourceRef

__all__ = ["CrimeCategoryWire", "NewsCrimeIncident", "NewsCrimeStatusWire"]

CrimeCategoryWire = Literal[
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
`crime_reports.category` verbatim, and the frontend's `CRIME_CATEGORIES` verbatim.

One vocabulary across a user's own report and a published one, so the map legend,
the filter chips and the marker colours are shared rather than duplicated. The
frontend file records what happened the last time these two drifted: every lookup
in `CRIME_COLORS` missed and no crime marker on the map had a colour.
"""

NewsCrimeStatusWire = Literal["published", "corroborated"]
"""
What the client can be served.

Narrower than the column's CHECK, which also allows `expired` and `removed`. Those
are terminal and are never served, so a client needs no branch for them, and a bug
that tried to serve one fails validation at the edge instead of painting a retired
incident on the map. Same arrangement as `ClusterStatusWire`.

`corroborated` is not a column value — the column stores `published` and a
`source_count` — it is derived on read from whether two or more *independent*
publishers carried the story. The wire says the thing the user cares about; the
table stores the thing the arithmetic needs.
"""


class NewsCrimeIncident(BaseModel):
    """
    One crime reported by one or more named publishers, as served to a client.

    `severity_now` rather than `severity_0`: what is served is always decayed to
    the instant of the request. The undecayed value never leaves the backend, for
    the reason the migration header gives — a client holding `severity_0` would
    draw the incident at full strength for ever, which is the single failure the
    whole decay design exists to prevent.
    """

    model_config = ConfigDict(frozen=True)

    incident_id: UUID
    category: CrimeCategoryWire
    status: NewsCrimeStatusWire

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    radius_m: int = Field(gt=0, le=1000)

    severity_now: float = Field(ge=0.0, le=100.0)
    observed_at: datetime

    statement: str = Field(min_length=1, max_length=160)
    """
    Produced only by `app/policy/attribution.py::to_attributed_statement`, and
    guaranteed by a database CHECK to name its publisher. The client renders it
    as-is and must never compose its own sentence from `category` — doing so would
    drop the attribution, which is the whole basis on which this surface may use
    crime vocabulary at all.
    """

    source_count: int = Field(ge=1)
    """Independent publishers, by `app/policy/independence.py`."""

    sources: list[SourceRef] = Field(default_factory=list)
    """
    The citations, so the client can link out. This is the surface's substance,
    not decoration: an attributed claim the reader cannot check is just a claim.
    """
