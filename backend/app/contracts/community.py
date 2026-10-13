"""
The community cluster contract — what a corroborated group of user reports looks
like on the wire.

Mirror: `frontend/src/types/contracts/community.ts`
Storage: `migrations/versions/20261013120100__community_clusters.sql`
Policy:  `app/policy/community.py`

A cluster is deliberately **not** a `RiskFlag`, and the reason is written out in
the migration header: a risk flag is a *mobility* claim, `MobilityImpact` has six
values and all six are about traffic flow, and a corner where people have been
robbed is not a road that is blocked. `app/policy/framing.py` closes the other
door by banning the vocabulary a report cluster would have to use.

So this is a sibling object with a narrower contract, and the narrowness is the
feature: compare the field list below with `RiskFlag`'s and note what is missing.
There is no `kind`, no `mobility_statement`, no `sources`, no category, no family
and no report ids. A cluster can say how many people, how close together, how
recently — and nothing else.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ClusterStatusWire", "CommunityCluster", "ReportRef"]

ClusterStatusWire = Literal["provisional", "corroborated"]
"""
What the client can be served.

Narrower than the column's CHECK, which also allows `expired` and `removed`. Those
are terminal states and are never served, so a client has no branch for them --
and a `Literal` here means a bug that tried to serve one would fail validation at
the edge rather than paint a retired cluster on the map.
"""


class ReportRef(BaseModel):
    """
    One contributing report, as stored in `community_clusters.reports`.

    **Backend-only. This never appears in an API response** — see
    `CommunityCluster`, which has no field for it. It exists so the corroboration
    agent can recount reporters on a later run without re-reading every report in
    the city, and so a published cluster can be audited after the fact.

    Three fields, and the omissions are the design:

    * `reporter_ref` is an HMAC of the author's user id keyed per cluster, **not**
      the user id. The agent needs to know "was this the same person as that
      one", which a stable per-cluster pseudonym answers, and it does not need to
      know who. Without this the table would be a map of who reported what, near
      where they live, which is a worse privacy surface than the reports it is
      derived from.
    * `incident_at` is the incident time, so the statement's "in the last N days"
      comes from data rather than a constant.
    * there is no title, description, category, family or photo. A cluster that
      cannot see a narrative cannot leak one.
    """

    model_config = ConfigDict(frozen=True)

    report_id: UUID
    reporter_ref: str = Field(min_length=8, max_length=64)
    incident_at: datetime


class CommunityCluster(BaseModel):
    """
    A decaying, located statement that several people independently reported
    something in one small area. The only community-report object a client sees.

    Three fields carry invariants rather than data, and all three mirror a
    `RiskFlag` field exactly so that the two objects decay and expire by the same
    rules:

    * `half_life_hours` — mandatory and positive. There are no permanent area
      labels in this product, and a cluster is the object most at risk of becoming
      one. The database carries the same CHECK.
    * `severity_now` — **computed on read, never stored.** `severity_0` is the
      severity at `observed_at`; this is that value decayed to the instant asked
      about, with the night-weighted hour multiplier applied. Required rather than
      optional, because a surface that forgot to compute it would serve a cluster
      that silently never fades.
    * `expires_at` — **derived** by `trg_community_clusters_expires_at`, which
      discards whatever a caller supplied. One rule, one place.

    `reporter_count` is the number that decides anything; `report_count` is the
    number of reports behind it and is always at least as large. Ten reports from
    two accounts is two people, and both numbers are served so the client can say
    so rather than implying ten witnesses.
    """

    cluster_id: UUID
    status: ClusterStatusWire
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(gt=0)

    # How many reports, and how many distinct people. See the class docstring.
    report_count: int = Field(ge=2)
    reporter_count: int = Field(ge=2)

    severity_0: float = Field(ge=0.0, le=100.0)
    severity_now: float = Field(ge=0.0, le=100.0)
    half_life_hours: float = Field(gt=0)

    observed_at: datetime  # the most recent contributing report
    first_report_at: datetime  # the oldest, so the statement can state a span
    expires_at: datetime  # derived, never hand-set

    # ONLY produced by `app.policy.community.to_cluster_statement`. A count and a
    # recency; never a category, never a characterisation.
    statement: str

    # When `reporter_count` first reached the corroboration threshold. A claim
    # about our own process, not about the events — the analogue of
    # `RiskFlag.confirmed_at`. Null on a provisional cluster.
    corroborated_at: datetime | None = None

    # How much of this cluster's severity should count in a decision, 0-1.
    #
    # **Derived from `status`, never stored**, by
    # `app.policy.community.confidence`. 0.3 provisional, 0.6 corroborated, and
    # there is no community-only route to 1.0.
    #
    # A field rather than something each consumer re-derives, for the reason
    # `RiskFlag.confidence` is: a policy decision duplicated in the route scorer
    # and again in TypeScript is a policy decision that will come to mean three
    # things. `severity_now` is deliberately not damped by it — consumers making a
    # decision want `severity_now * confidence`, which is
    # `app.scoring.decay.effective_severity`.
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)
