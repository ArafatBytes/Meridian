"""
Path scoring over the `RiskSurface` protocol. S12, and defects 6, 8 and 11.

One scale, stated once: **`safety_score` is 0–100 and higher is safer.** There is no
`crime_score`, no 0–10 variant, and no percentage. Defect 11 existed because there were
three of them — a 0–10 `RouteSegment.crime_score`, a 0–100 `safety_score`, and a UI that
rendered the latter as "`58.3% Safe`" — and no two of them agreed about what a number
meant.

---

## What this module does and does not decide

It decides **what a corridor is worth**: how much a flag detracts, how distance trades
against safety, and where the cut-off for "do not route through this" sits. All of that is
tunable in `settings` rather than being a literal in the middle of a function, because
S12 asks for a composite that is *"documented and tunable in settings, not a magic
constant"*.

It does **not** decide what is near the route. That is `RiskSurface.flags_near_path`, and
routing never touches a table — which is what lets the whole module work unchanged on
`RISK_SURFACE_IMPL=seeded` for the offline demo. S12's own check.

## ⚠️ `confidence`, and the mistake this module exists to avoid

D05 published unconfirmed flags at reduced weight and left a warning for this sprint:
scoring must use `decay.effective_severity(severity_now, confidence)`, **not**
`severity_now`. If it used the raw value, a single-source rumour would bend a route
exactly as hard as a fact corroborated by three publishers, and D05's whole verification
tier would be decoration.

It is the easiest thing here to get wrong because the failure is invisible — routes still
look plausible, they are just quietly wrong — so there is a test asserting that an
unconfirmed flag moves a score less than an identical confirmed one.

## Why the chronic layer is not handled here

It already arrives through the surface. D02 wired `scripts/crime_risk_model.json` in as
chronic flags, so `flags_near_path` returns them alongside news flags and they are scored
by the same arithmetic. That is why `route_service._get_regional_risk()` had to go: it
applied the same police statistics a second time, from a second code path, and the symptom
was a plausible-looking score that was quietly doubled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from app.contracts.community import CommunityCluster
from app.contracts.news_crime import NewsCrimeIncident
from app.contracts.risk import IncidentKind, RiskFlag
from app.contracts.surface import ClusterSurface, NewsCrimeSurface, RiskSurface
from app.core.config import settings
from app.policy.attribution import weight_for
from app.scoring.decay import effective_severity

logger = logging.getLogger(__name__)

__all__ = ["ScoredPath", "score_path"]


MAX_SAFETY: Final[float] = 100.0
"""The top of the one scale. 0 is as bad as a route gets; 100 is nothing known against it."""


@dataclass(frozen=True)
class ScoredPath:
    """
    A path, scored, with the evidence that produced the score.

    `flags` is the evidence, not decoration: `routing/explain.py` builds the
    plain-English sentence from it, and the client draws it on the rejected route so the
    comparison reads without narration. A score with no attached reason is exactly the
    kind of number a judge should distrust.
    """

    safety_score: float  # 0-100, higher is safer. The only scale.
    composite_score: float  # safety traded against duration, for ranking
    flags: list[RiskFlag]  # worst first, already weighted by confidence
    risk_penalty: float  # what was subtracted from MAX_SAFETY, for debugging

    # B13. Community report clusters along the same corridor, worst first.
    #
    # A separate list rather than more entries in `flags`, for the reason
    # `app/contracts/surface.py::ClusterSurface` gives: these are a different kind
    # of claim, and a caller that cannot tell them apart will present them
    # identically. `routing/explain.py` needs that distinction to write an honest
    # sentence -- "three people reported incidents here" and "the fire service
    # closed this road" are not the same statement and must not share a phrasing.
    #
    # Empty when no `ClusterSurface` was passed, which is the offline path.
    clusters: list[CommunityCluster] = field(default_factory=list)

    # S30. Crime reported by named publishers along the same corridor, worst first.
    #
    # A third list for the third kind of claim, and the same argument as above: a
    # caller that cannot tell these apart will present them identically, and
    # "Prothom Alo reported a robbery here" is not "three people reported
    # incidents here" and is not "the fire service closed this road". Each needs
    # its own phrasing in `routing/explain.py` because each is true in a different
    # way.
    #
    # Empty when no `NewsCrimeSurface` was passed, which is the offline path.
    news_crime: list[NewsCrimeIncident] = field(default_factory=list)


def _penalty_for(flag: RiskFlag) -> float:
    """
    How much one flag detracts from a route's safety.

    Two multipliers, and both exist for a reason that is easy to get wrong:

    **`confidence`**, via `effective_severity` and never `severity_now` — see the module
    docstring. An `unconfirmed` flag carries 0.6, so it is counted at 60% of its decayed
    severity: published, weighed, not obeyed.

    **`ROUTE_CHRONIC_WEIGHT`** for `kind == chronic`. The chronic layer is a historical
    average over 2 km radii covering most of Dhaka, and at full weight it swamped
    everything: a 12.6 km crossing passing three chronic flags scored **16.7/100**, every
    route in the city scored about the same, and `max_crime_score` rejected all of them --
    so defect 6's filter did nothing and the ranking reflected historical coverage rather
    than today's events.

    That is not merely badly tuned, it is the **"stale red zones"** failure demo beat 5
    exists to disclaim, and concept document section 9 commits to not labelling areas
    permanently. A historical average should nudge a tie-break between two routes; a fire
    that started an hour ago should decide one. At 0.35 the same crossing scores 68.6 and a
    live event moves it visibly.
    """
    penalty = effective_severity(severity_now=flag.severity_now, confidence=flag.confidence)
    if flag.kind == IncidentKind.CHRONIC:
        penalty *= max(0.0, min(1.0, settings.ROUTE_CHRONIC_WEIGHT))
    return penalty


def _penalty_for_cluster(cluster: CommunityCluster) -> float:
    """
    How much one community cluster detracts from a route's safety. B13.

    The same arithmetic as `_penalty_for`, through the same `effective_severity`, so
    a cluster and a flag are commensurable and `_combine` can rank them together.
    What differs is where the numbers come from: a cluster's `confidence` is 0.3 or
    0.6 from `app/policy/community.py`, against a flag's 0.6 or 1.0, and its
    `severity_0` is capped at 55 against a fire's 70.

    Those two caps are what keep the ordering right without a third weight here.
    Three independent reporters produce at most 55 x 0.6 = 33, so a live fire at
    70 x 1.0 always outranks a corroborated cluster, and a cluster still moves a
    score visibly. There is deliberately no `ROUTE_CLUSTER_WEIGHT` setting: the
    tier weights already live in one place, and a second multiplier here would mean
    the published weight of a cluster is not the weight it is scored at.
    """
    return effective_severity(
        severity_now=cluster.severity_now, confidence=cluster.confidence
    )


def _penalty_for_news_crime(incident: NewsCrimeIncident) -> float:
    """
    How much one published crime report detracts from a route's safety. S30.

    The same arithmetic as the other two, through the same `effective_severity`, so
    all three are commensurable and `_combine` can rank them together. The
    confidence is `app/policy/attribution.py::weight_for` — 0.35 for one publisher,
    0.7 for two or more independent ones.

    Where this sits in the ordering, and why it is deliberate:

        a live fire, confirmed        70 x 1.0  = 70.0
        a corroborated robbery        60 x 0.7  = 42.0
        a corroborated user cluster   55 x 0.6  = 33.0
        a single-publisher robbery    60 x 0.35 = 21.0
        reported fraud                10 x 0.35 =  3.5

    So a road closed by the fire service still outranks everything, two newspapers
    agreeing on a street robbery outweighs three anonymous app users agreeing, and
    one newspaper's account sits below that — published, weighed, not obeyed. That
    ordering is the whole claim of this surface expressed as arithmetic: a named
    masthead is a stronger single source than an anonymous one, and still weaker
    than several sources agreeing.

    There is deliberately no `ROUTE_NEWS_CRIME_WEIGHT` setting, for the reason
    `_penalty_for_cluster` gives: the tier weights already live in one place, and a
    second multiplier here would mean the published weight is not the scored weight.
    """
    return effective_severity(
        severity_now=incident.severity_now, confidence=weight_for(incident.source_count)
    )


def _combine(penalties: list[float]) -> float:
    """
    Several flags into one penalty, with **diminishing returns**.

    Summing is wrong, and wrong in a way that matters on a long route. Ten minor flags
    along a 12 km corridor would sum past any threshold and make every route across Dhaka
    score zero — at which point the ranking carries no information and the map is just
    red. Averaging is also wrong, in the other direction: it lets one severe flag be
    diluted by a dozen trivial ones, which is precisely the case a traveller needs to be
    warned about.

    So: the worst flag counts in full, and each subsequent one contributes a geometrically
    shrinking share. The worst thing on the route dominates, additional problems still
    make it worse, and the total cannot run away.
    """
    if not penalties:
        return 0.0
    ordered = sorted(penalties, reverse=True)
    decay = settings.ROUTE_PENALTY_FALLOFF
    return sum(penalty * (decay**index) for index, penalty in enumerate(ordered))


def _duration_score(duration_s: float, fastest_s: float) -> float:
    """
    How this route's duration compares with the fastest option, 0-100.

    Relative, not absolute. An absolute scale needs a notion of "a long journey" that does
    not exist — 40 minutes is unremarkable across Dhaka and absurd for three streets — so
    the fastest route available scores 100 and the others are penalised in proportion to
    how much longer they take.

    `ROUTE_DETOUR_TOLERANCE` sets how much slower a route may be before it scores zero on
    this axis. At the default 1.0, a route taking twice as long scores 0.
    """
    if fastest_s <= 0:
        return MAX_SAFETY
    overhead = (duration_s - fastest_s) / fastest_s
    tolerance = max(0.01, settings.ROUTE_DETOUR_TOLERANCE)
    return max(0.0, MAX_SAFETY * (1.0 - overhead / tolerance))


def composite(safety_score: float, duration_s: float, fastest_s: float) -> float:
    """
    The ranking number: safety traded against time.

    Weighted by `ROUTE_SAFETY_WEIGHT` (default 0.7), so safety dominates but does not win
    outright — a route that is marginally safer and twice as long is not the one to
    recommend, and a product that always returns the longest route stops being used.

    Both inputs are already on the same 0-100 scale, which is the point of defect 11.
    """
    weight = min(1.0, max(0.0, settings.ROUTE_SAFETY_WEIGHT))
    return safety_score * weight + _duration_score(duration_s, fastest_s) * (1.0 - weight)


async def score_path(
    surface: RiskSurface,
    *,
    path: list[tuple[float, float]],
    at: datetime,
    clusters: ClusterSurface | None = None,
    news_crime: NewsCrimeSurface | None = None,
) -> ScoredPath:
    """
    Score one path against the risk surface, and against community clusters when a
    `ClusterSurface` is supplied.

    `composite_score` is left at 0.0 here and filled in by the caller, because it is
    **relative to the other candidates** — a route cannot know whether it is the fastest
    until the alternatives exist. Computing it per-path would need a guess at what "fast"
    means, which is the absolute-scale mistake `_duration_score` avoids.

    `clusters` is optional, and `None` must stay a supported value: there is no seeded
    cluster surface, so the offline demo path passes nothing and gets a route scored
    against news flags alone. That is the honest result in that mode -- no reports have
    been filed into a fixture.

    **Flags and clusters go into one `_combine` call, not two.** Scoring them separately
    and adding the results would lose the diminishing-returns property for the total: a
    corridor with three flags and three clusters would be penalised as two independent
    worst-cases, and a long route across Dhaka would floor at zero again, which is
    exactly the failure `_combine` exists to prevent. Combined, the worst single thing
    on the route dominates whichever kind it is -- which is also the right answer for a
    traveller, who does not care what sort of object the problem is.
    """
    flags = await surface.flags_near_path(path, settings.ROUTE_CORRIDOR_RADIUS_M, at)
    found_clusters: list[CommunityCluster] = []
    if clusters is not None:
        found_clusters = await clusters.clusters_near_path(
            path, settings.ROUTE_CORRIDOR_RADIUS_M, at
        )

    found_crime: list[NewsCrimeIncident] = []
    if news_crime is not None:
        found_crime = await news_crime.crimes_near_path(
            path, settings.ROUTE_CORRIDOR_RADIUS_M, at
        )

    penalties = [_penalty_for(flag) for flag in flags]
    penalties += [_penalty_for_cluster(cluster) for cluster in found_clusters]
    penalties += [_penalty_for_news_crime(incident) for incident in found_crime]
    penalty = _combine(penalties)
    safety = max(0.0, MAX_SAFETY - penalty)

    logger.debug(
        "scored path: %d point(s), %d flag(s), %d cluster(s), %d crime, "
        "penalty %.1f, safety %.1f",
        len(path),
        len(flags),
        len(found_clusters),
        len(found_crime),
        penalty,
        safety,
    )
    return ScoredPath(
        safety_score=round(safety, 1),
        composite_score=0.0,
        flags=flags,
        risk_penalty=round(penalty, 1),
        clusters=found_clusters,
        news_crime=found_crime,
    )


def passes_filters(
    scored: ScoredPath,
    *,
    avoid_high_crime_zones: bool,
    max_crime_score: int | None,
) -> bool:
    """
    Defect 6: `avoid_high_crime_zones` and `max_crime_score` were accepted and ignored.

    Both are honoured now. The naming is awkward and kept deliberately: they are public
    request fields, and renaming them to match defect 11's single scale would break any
    client already sending them. What they mean is pinned down instead —

    * `avoid_high_crime_zones` — when false, no filtering happens at all and every route
      is returned, scored and ranked. Someone who has turned the feature off should get
      routes, not an empty list.
    * `max_crime_score` — a ceiling on `100 - safety_score`, so the default 75 rejects any
      route scoring below 25 on safety. One scale internally; the parameter is expressed
      on its inverse because that is the name it already had.

    **A filter that rejects everything is not applied** — see `apply_filters`. Returning
    no route to someone asking how to get home is the worst possible answer.
    """
    if not avoid_high_crime_zones or max_crime_score is None:
        return True
    return (MAX_SAFETY - scored.safety_score) <= float(max_crime_score)


def apply_filters(
    scored: list[ScoredPath],
    *,
    avoid_high_crime_zones: bool,
    max_crime_score: int | None,
) -> tuple[list[bool], bool]:
    """
    A keep-mask for defect 6's filters, and whether the filter had to be relaxed.

    Returns `(keep, filter_relaxed)` with one boolean per input, in order. A mask rather
    than a filtered list because the caller holds the routes these scores belong to, and
    pairing them back up by object identity afterwards is the kind of cleverness that
    breaks the first time a score is recomputed.

    **When every candidate fails the ceiling, everything is kept and `filter_relaxed` is
    true.** This is the one place the semantics could reasonably go either way, so: a
    routing app that answers "no acceptable route" when every road to your destination
    passes something flagged has stopped being a routing app. Telling the traveller that
    all available routes exceed their threshold, and then showing them best-first, is
    honest and useful. Silently dropping the preference would be neither, which is why the
    flag is returned rather than swallowed.
    """
    keep = [
        passes_filters(
            path_score,
            avoid_high_crime_zones=avoid_high_crime_zones,
            max_crime_score=max_crime_score,
        )
        for path_score in scored
    ]
    if any(keep) or not scored:
        return keep, False

    logger.info(
        "every route exceeded max_crime_score=%s; returning all %d rather than none",
        max_crime_score,
        len(scored),
    )
    return [True] * len(scored), True
