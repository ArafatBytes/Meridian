"""
Route calculation schemas.

**One scale: `safety_score`, 0–100, higher is safer.** D06 deleted the other two.
`RouteSegment.crime_score` was 0–10, `safety_score` was 0–100, and the app rendered the
latter as `58.3% Safe` — three readings of one quantity, none of which agreed, which is
defect 11. If you need the inverse, write `100 - safety_score` where you use it.
"""

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    source: Location
    destination: Location

    avoid_high_crime_zones: bool = True
    """
    Whether to reject routes above `max_crime_score`.

    Honoured since D06 — defect 6 was that this and `max_crime_score` were accepted and
    silently ignored. When false, no filtering happens and every route comes back scored
    and ranked.
    """

    max_crime_score: int | None = Field(default=75, ge=0, le=100)
    """
    Ceiling on `100 - safety_score`. The default 75 rejects routes scoring below 25.

    The name predates D06's single-scale rule and is kept because it is a public request
    field that clients may already send; it is the same scale read backwards, not a second
    one. **A filter that would reject every route is relaxed rather than applied** — see
    `RouteResponse.filter_relaxed`.
    """

    profile: str = "driving"
    """
    `driving` or `foot`. D06 added the walking profile — defect 7.

    ⚠️ Walking routes are currently answered from a `car.lua` graph, so they obey car turn
    restrictions and may use a flyover. `app/routing/osrm.py :: WALKING_GRAPH_CAVEAT` says
    so and logs it on every request.
    """


class RouteSegment(BaseModel):
    """
    One point on a route's drawn path.

    Carries no score. It used to have a 0–10 `crime_score` per point, which was defect 11:
    a per-point risk number that was really `(100 - route_safety) / 10` repeated for every
    point, so it conveyed nothing the route-level score did not and did it on a third
    scale. Risk is a property of the corridor, and the flags that justify it are in
    `RouteResponse.flags`.
    """

    latitude: float
    longitude: float


class RouteFlag(BaseModel):
    """
    A flag on this route, as the client needs to draw and explain it.

    A deliberate subset of `RiskFlag` rather than the whole contract: the route card needs
    the statement, where it is, how corroborated it is and how bad it is now. Returning the
    full flag would ship `event_key`, `time_profile` and `expires_at` to a card that cannot
    use them, and would couple the route response to every future change in the risk
    contract.
    """

    flag_id: str
    lat: float
    lon: float
    radius_m: int
    mobility_statement: str  # framed server-side; render as-is, never rebuild it
    severity_now: float = Field(ge=0.0, le=100.0)
    status: str  # "confirmed" | "unconfirmed"
    source_count: int = Field(ge=1)

    kind: str
    """
    The incident kind, carried so the client can separate **what is happening now** from
    **what has always been true here**.

    `chronic` is the historical police-statistics baseline, not an event: it has no
    headline, it will still be there next month, and it is scored at
    `ROUTE_CHRONIC_WEIGHT`. A card that presented it identically to a fire reported an
    hour ago would be making exactly the permanent-area-label claim concept document
    section 9 rules out.
    """


class RouteStep(BaseModel):
    """
    One manoeuvre, as the navigation banner needs it.

    From OSRM's `steps=true`, via `app/routing/osrm.py::OsrmStep`. The client
    previously derived turns from the shape of the polyline, which gives a reliable
    side and distance and cannot name a road; this is what lets it say "Turn left
    onto Mirpur Road".

    ## `name` is optional in practice, whatever the type says

    It is `str` rather than `str | None` because OSRM sends `""` for an unnamed way,
    and a great many Dhaka lanes, service roads and residential streets have no OSM
    `name` tag at all. **Every consumer must check it before using it** -- the
    client falls back to the geometric phrasing ("Turn left in 80 m") when it is
    empty, which is the honest answer rather than "Turn left onto" trailing off.

    ## `start_m` is derived here, not sent by OSRM

    OSRM gives each step a distance but no position along the route, and the client
    needs "which step am I on" from a single number it already has
    (`progress.alongM`). So the backend accumulates the step distances into an offset
    from the route's start, and **scales them to the route's own total** -- the sum
    of step distances and the route's reported distance differ by a few metres from
    rounding, and without the scaling the last manoeuvre would sit slightly past the
    end of the polyline the client is measuring against.
    """

    name: str
    """The OSM road name, or "" when the way has none. Check before using."""

    maneuver_type: str
    """
    OSRM's own vocabulary: `turn`, `new name`, `depart`, `arrive`, `roundabout`,
    `fork`, `merge`, `end of road`, `continue`, `on ramp`, `off ramp`.

    Carried verbatim rather than mapped to a sentence here. The mapping is a
    presentation decision and belongs with the component that renders it, next to
    the fallback it shares with the geometric path.
    """

    modifier: str
    """`left`, `right`, `slight left`, `sharp right`, `straight`, `uturn`, or ""."""

    distance_m: float = Field(ge=0)
    duration_s: float = Field(ge=0)

    start_m: float = Field(ge=0)
    """Distance from the route's start to where this step BEGINS. Derived; see above."""

    lat: float
    lon: float
    """Where the manoeuvre happens -- the end of the previous step."""


class RouteCluster(BaseModel):
    """
    A community report cluster on this route, as the card needs it. B13.

    A deliberate subset of `CommunityCluster`, for the reason `RouteFlag` is a subset
    of `RiskFlag`: the card needs where it is, how many people, how corroborated and
    how much it weighs now. `half_life_hours`, `expires_at` and `first_report_at` are
    the decay story the map's detail sheet narrates, and a route card cannot use them.

    Note what is **not** here, and could not be added later without a migration: no
    category, no family, no report ids, no narrative. A cluster has nothing to say
    about what happened -- only that several people independently said something did.
    """

    cluster_id: str
    lat: float
    lon: float
    radius_m: int

    statement: str
    """
    The published form, from `app/policy/community.py::to_cluster_statement`. A count
    and a recency. Render as-is; never rebuild it on the client.
    """

    severity_now: float = Field(ge=0.0, le=100.0)

    status: str
    """
    `provisional` (2 independent reporters) or `corroborated` (3 or more).

    Carried so the card can render the two tiers differently, the way the map
    distinguishes `confirmed` from `unconfirmed` flags. Presenting two accounts
    identically to three would make the tiers decoration.
    """

    report_count: int = Field(ge=2)
    reporter_count: int = Field(ge=2)
    """
    Both, because they are different facts and the difference is the honest part:
    ten reports from two accounts is two people, and a card showing only the first
    number would imply ten witnesses.
    """


class RouteResponse(BaseModel):
    route_id: str
    path: list[RouteSegment]
    distance_km: float

    duration_minutes: int
    """
    **OSRM's own duration**, from the road graph.

    Was `distance_km * 60 / 30` — a flat 30 km/h assumption, wrong in both directions and
    wrong while OSRM had already answered the question. Half of defect 7.
    """

    safety_score: float = Field(ge=0.0, le=100.0)
    """0–100, higher is safer. The only scale."""

    composite_score: float = Field(ge=0.0, le=100.0)
    """
    The ranking number: `safety_score` traded against duration.

    Weighted by `ROUTE_SAFETY_WEIGHT`, and the duration axis is **relative to the fastest
    candidate** — which is why a single route cannot compute its own composite.
    """

    flags: list[RouteFlag]
    """
    The risk flags along this corridor, worst first.

    The evidence behind `safety_score`, and what the client highlights on a rejected route
    so the comparison reads without narration. A score with no attached reason is the kind
    of number a judge should distrust.
    """

    steps: list[RouteStep] = Field(default_factory=list)
    """
    Turn-by-turn manoeuvres in travel order, for live navigation.

    Empty for the straight-line fallback, which is not a road route and has no
    manoeuvres to describe, and empty if OSRM returned none. The client treats an
    empty list as "narrate from the geometry instead", which is what it did before
    this field existed -- so a router that cannot supply steps degrades to plainer
    directions rather than to no directions.
    """

    clusters: list[RouteCluster] = Field(default_factory=list)
    """
    Community report clusters along this corridor, worst first. B13.

    A separate list from `flags`, never merged into it. The two are different claims --
    a flag is the product's own mobility claim derived from edited sources, a cluster is
    a count of what residents reported -- and Defect 54 is the log of what happens when
    a surface draws them as the same thing.

    Empty on the offline path, which has no cluster surface. Empty is also the normal
    answer: most corridors have no clusters, because publishing one needs at least two
    independent people to have filed reports within 200 m of each other.
    """

    explanation: str
    """
    One sentence of plain English. Demo beat 4.

    Assembled by `app/routing/explain.py` from each flag's `mobility_statement` plus the
    source count, then checked by the framing guard. Never written by an LLM, never
    composed on the client.
    """

    engine: str
    """
    `local`, `public-demo` or `straight-line`.

    Which engine answered. `public-demo` means the local OSRM did not respond and a
    rate-limited third party was used instead; `straight-line` means neither did and this
    is a crude estimate, not a route. Surfaced rather than logged so the walkthrough can
    assert it and the demo cannot quietly degrade.
    """

    filter_relaxed: bool = False
    """
    True when every route exceeded `max_crime_score` and the preference was dropped.

    Honest rather than silent: the alternative is answering "no acceptable route" to
    someone asking how to get home.
    """

    notes: list[str] = Field(default_factory=list)
    """
    Caveats about **how this answer was produced** — for the user, in plain words.

    Deliberately separate from `explanation`, and the distinction is not cosmetic.
    `explanation` is a claim about the city and is therefore framing-guarded prose owned by
    `app/policy/framing.py`. These are claims about *us*: which graph answered, that a
    preference was relaxed, that a duration is an estimate. Mixing them would put system
    chatter through a guard designed for statements about places, and would let a caveat be
    mistaken for something we are saying about a neighbourhood.

    Empty on a clean driving route, which is the common case.
    """

    class Config:
        from_attributes = True
