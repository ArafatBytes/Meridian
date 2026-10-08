"""
Route scoring: one scale, confidence honoured, filters that do not strand the user.

D06, sources S12 and S13, and defects 6, 7, 8 and 11. The tests are grouped by the thing
that would be silently wrong if they were missing — all four of these failures produce a
plausible-looking number, which is why they are tests rather than careful reading.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contracts.risk import IncidentKind, RiskFlag
from app.core.config import settings
from app.policy.framing import FramingViolation
from app.routing.alternatives import detour_waypoints, worst_live_flag
from app.routing.explain import (
    MAX_EXPLANATION_LENGTH,
    assert_explanation_safe,
    explain_route,
    trade_off_sentence,
)
from app.routing.scorer import MAX_SAFETY, apply_filters, composite, passes_filters
from app.scoring.geometry import (
    CORRIDOR_SIMPLIFY_M,
    distance_to_segment_m,
    haversine_m,
    simplify_for_corridor,
)

pytestmark = pytest.mark.invariant

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def flag(
    *,
    severity_now: float = 60.0,
    status: str = "confirmed",
    confidence: float = 1.0,
    kind: IncidentKind = IncidentKind.FIRE,
    source_count: int = 3,
    lat: float = 23.75,
    lon: float = 90.40,
    radius_m: int = 400,
    statement: str = "Road blocked near Bangshal.",
) -> RiskFlag:
    """A `RiskFlag` with everything the scorer reads and nothing it does not."""
    return RiskFlag(
        flag_id=uuid4(),
        event_key="test",
        kind=kind,
        status=status,  # type: ignore[arg-type]
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        severity_0=severity_now,
        severity_now=severity_now,
        half_life_hours=3.0,
        observed_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=6),
        source_count=source_count,
        sources=[],
        mobility_statement=statement,
        confidence=confidence,
    )


class _Surface:
    """A `RiskSurface` that returns what the test hands it. No database, no fixture."""

    def __init__(self, flags: list[RiskFlag]) -> None:
        self._flags = flags
        self.last_radius_m: int | None = None

    async def flags_in_bbox(self, *args: object, **kwargs: object) -> list[RiskFlag]:
        return self._flags

    async def flags_near(self, *args: object, **kwargs: object) -> list[RiskFlag]:
        return self._flags

    async def flags_near_path(
        self, path: object, radius_m: int, at: datetime
    ) -> list[RiskFlag]:
        self.last_radius_m = radius_m
        return self._flags


# ---------------------------------------------------------------------------
# D05's warning: confidence must reach the score
# ---------------------------------------------------------------------------


async def test_an_unconfirmed_flag_bends_a_route_less_than_a_confirmed_one() -> None:
    """
    **The test D05 asked D06 to write.** Scoring must use
    `decay.effective_severity(severity_now, confidence)`, not `severity_now`.

    If it used the raw value, a single-source rumour would bend a route exactly as hard as
    a fact three publishers agree on, and D05's verification tier would be decoration. The
    failure is invisible — routes still look plausible — so nothing but a test catches it.
    """
    from app.routing.scorer import score_path

    path = [(23.70, 90.40), (23.80, 90.40)]
    confirmed = await score_path(
        _Surface([flag(status="confirmed", confidence=1.0)]), path=path, at=NOW
    )
    unconfirmed = await score_path(
        _Surface([flag(status="unconfirmed", confidence=0.6)]), path=path, at=NOW
    )

    assert unconfirmed.safety_score > confirmed.safety_score, (
        "an unconfirmed flag must cost a route less than an identical confirmed one; "
        "scorer is probably using severity_now instead of effective_severity"
    )
    assert unconfirmed.risk_penalty == pytest.approx(confirmed.risk_penalty * 0.6, rel=0.02)


async def test_a_chronic_flag_counts_less_than_a_live_one() -> None:
    """
    The chronic layer is a historical average, not an event.

    At full weight it swamped everything: a 12.6 km Dhaka crossing passing three chronic
    flags scored **16.7/100**, every route in the city scored about the same, and
    `max_crime_score` therefore rejected all of them — so defect 6's filter did nothing.
    That is the "stale red zones" failure demo beat 5 exists to disclaim.
    """
    from app.routing.scorer import score_path

    path = [(23.70, 90.40), (23.80, 90.40)]
    live = await score_path(_Surface([flag(kind=IncidentKind.FIRE)]), path=path, at=NOW)
    chronic = await score_path(_Surface([flag(kind=IncidentKind.CHRONIC)]), path=path, at=NOW)

    assert chronic.safety_score > live.safety_score
    assert chronic.risk_penalty == pytest.approx(
        live.risk_penalty * settings.ROUTE_CHRONIC_WEIGHT, rel=0.02
    )


# ---------------------------------------------------------------------------
# Defect 11: one scale
# ---------------------------------------------------------------------------


def test_safety_score_is_the_only_scale_on_the_response() -> None:
    """
    `RouteSegment` carries no score and `RouteResponse` carries exactly one.

    Defect 11 was three readings of one quantity — a 0–10 `RouteSegment.crime_score`, a
    0–100 `safety_score`, and a UI rendering the latter as `58.3% Safe` — none of which
    agreed. Asserted against the schema so re-adding a second scale fails here.
    """
    from app.schemas.route import RouteResponse, RouteSegment

    assert "crime_score" not in RouteSegment.model_fields
    assert set(RouteSegment.model_fields) == {"latitude", "longitude"}

    scales = {
        name
        for name in RouteResponse.model_fields
        if "score" in name and name not in {"composite_score"}
    }
    assert scales == {"safety_score"}, f"more than one risk scale on the response: {scales}"


async def test_a_clean_route_scores_full_marks() -> None:
    from app.routing.scorer import score_path

    scored = await score_path(_Surface([]), path=[(23.70, 90.40), (23.80, 90.40)], at=NOW)
    assert scored.safety_score == MAX_SAFETY
    assert scored.risk_penalty == 0.0


async def test_penalties_have_diminishing_returns() -> None:
    """
    Many small flags must not drive every long route to zero.

    Summing penalties is the obvious implementation and it is wrong: ten minor flags along
    a 12 km corridor would exceed any threshold, every route across Dhaka would score 0,
    and the ranking would carry no information at all. Averaging fails the other way — one
    severe flag diluted by a dozen trivial ones is exactly the case to warn about.
    """
    from app.routing.scorer import score_path

    path = [(23.70, 90.40), (23.80, 90.40)]
    many = await score_path(_Surface([flag(severity_now=20.0) for _ in range(10)]), path=path, at=NOW)
    one_bad = await score_path(_Surface([flag(severity_now=80.0)]), path=path, at=NOW)

    assert many.safety_score > 0.0, "ten minor flags must not zero a route"
    assert one_bad.safety_score < many.safety_score, (
        "one severe flag should outweigh ten minor ones; the combination is diluting it"
    )


# ---------------------------------------------------------------------------
# Defect 6: the filters are honoured, and do not strand the user
# ---------------------------------------------------------------------------


def _scored(safety: float):
    from app.routing.scorer import ScoredPath

    return ScoredPath(safety_score=safety, composite_score=0.0, flags=[], risk_penalty=0.0)


def test_max_crime_score_is_a_ceiling_on_the_inverse_of_safety() -> None:
    """`max_crime_score=75` rejects anything scoring below 25 on safety. Defect 6."""
    assert passes_filters(_scored(30.0), avoid_high_crime_zones=True, max_crime_score=75)
    assert not passes_filters(_scored(20.0), avoid_high_crime_zones=True, max_crime_score=75)


def test_turning_the_preference_off_disables_the_filter() -> None:
    """Someone who has turned the feature off should get routes, not an empty list."""
    assert passes_filters(_scored(1.0), avoid_high_crime_zones=False, max_crime_score=75)
    assert passes_filters(_scored(1.0), avoid_high_crime_zones=True, max_crime_score=None)


def test_a_filter_that_would_reject_everything_is_relaxed_instead() -> None:
    """
    The one place the semantics could go either way, pinned down.

    A routing app that answers "no acceptable route" when every road to your destination
    passes something flagged has stopped being a routing app. Everything is returned and
    `filter_relaxed` says so, which is honest; silently dropping the preference would not
    be.
    """
    keep, relaxed = apply_filters(
        [_scored(10.0), _scored(5.0)], avoid_high_crime_zones=True, max_crime_score=75
    )
    assert keep == [True, True]
    assert relaxed is True


def test_a_filter_with_a_survivor_is_applied_normally() -> None:
    keep, relaxed = apply_filters(
        [_scored(90.0), _scored(5.0)], avoid_high_crime_zones=True, max_crime_score=75
    )
    assert keep == [True, False]
    assert relaxed is False


# ---------------------------------------------------------------------------
# The composite, and the tunables
# ---------------------------------------------------------------------------


def test_the_composite_prefers_safety_without_ignoring_time() -> None:
    """
    Safety dominates but does not win outright.

    A route marginally safer and twice as long is not the one to recommend, and a product
    that always returns the longest route stops being used.
    """
    safe_slow = composite(90.0, duration_s=3600, fastest_s=600)
    ok_fast = composite(70.0, duration_s=600, fastest_s=600)
    assert ok_fast > safe_slow, "a 6x detour for 20 points of safety should not win"

    much_safer = composite(95.0, duration_s=700, fastest_s=600)
    assert much_safer > ok_fast, "a slightly longer, much safer route should win"


def test_the_tunables_are_settings_not_literals() -> None:
    """
    S12: *"a composite that is documented and tunable in settings, not a magic constant."*

    A float buried in a scoring function is a value nobody can find, review or change.
    """
    for name in (
        "ROUTE_CORRIDOR_RADIUS_M",
        "ROUTE_SAFETY_WEIGHT",
        "ROUTE_PENALTY_FALLOFF",
        "ROUTE_DETOUR_TOLERANCE",
        "ROUTE_CHRONIC_WEIGHT",
    ):
        assert hasattr(settings, name), f"{name} must be a setting, not a literal"

    assert 0.0 <= settings.ROUTE_SAFETY_WEIGHT <= 1.0
    assert 0.0 < settings.ROUTE_PENALTY_FALLOFF < 1.0
    assert 0.0 < settings.ROUTE_CHRONIC_WEIGHT < 1.0


async def test_scoring_asks_the_surface_for_the_configured_corridor() -> None:
    """Routing must not invent its own radius; the setting is the one knob."""
    from app.routing.scorer import score_path

    surface = _Surface([])
    await score_path(surface, path=[(23.70, 90.40), (23.80, 90.40)], at=NOW)
    assert surface.last_radius_m == settings.ROUTE_CORRIDOR_RADIUS_M


# ---------------------------------------------------------------------------
# Defect 8's geometry
# ---------------------------------------------------------------------------


def test_distance_is_measured_to_the_segment_not_the_vertices() -> None:
    """
    The reason `flags_near_path` is not a vertex check.

    A route thinned to one point every 120 m, tested only at its vertices, would miss
    anything beside the middle of a straight run — which is where a long road's flags sit.
    `ST_DWithin` against a LINESTRING measures to the segment, so the seeded surface must
    too, or the two surfaces disagree.
    """
    # A point beside the midpoint of a ~1.1 km north-south segment.
    midpoint_offset = distance_to_segment_m(23.755, 90.4010, 23.750, 90.4000, 23.760, 90.4000)
    to_nearest_vertex = min(
        haversine_m(23.755, 90.4010, 23.750, 90.4000),
        haversine_m(23.755, 90.4010, 23.760, 90.4000),
    )
    assert midpoint_offset < 150.0
    assert to_nearest_vertex > 500.0, "the fixture should be far from both vertices"


def test_a_point_past_an_endpoint_measures_to_that_endpoint() -> None:
    """Clamped projection: not to the infinite line the segment lies on."""
    beyond = distance_to_segment_m(23.90, 90.40, 23.750, 90.40, 23.760, 90.40)
    assert beyond == pytest.approx(haversine_m(23.90, 90.40, 23.760, 90.40), rel=0.01)


def test_simplification_keeps_the_endpoints_and_cannot_move_the_line() -> None:
    """
    Distance-thinning, not Douglas-Peucker.

    Every retained point is an original point, so the corridor cannot shift; a
    shape-preserving simplifier may cut a corner, and a cut corner is a stretch of road
    that silently stops being tested.
    """
    dense = [(23.70 + index * 0.0002, 90.40) for index in range(60)]
    thinned = simplify_for_corridor(dense)

    assert thinned[0] == dense[0]
    assert thinned[-1] == dense[-1]
    assert len(thinned) < len(dense)
    assert all(point in dense for point in thinned), "thinning must not invent a point"

    spacings = [
        haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(thinned, thinned[1:])
    ]
    assert min(spacings[:-1] or [CORRIDOR_SIMPLIFY_M]) >= CORRIDOR_SIMPLIFY_M * 0.95


def test_a_degenerate_path_is_not_a_corridor() -> None:
    assert simplify_for_corridor([]) == []
    assert len(simplify_for_corridor([(23.7, 90.4)])) == 1


# ---------------------------------------------------------------------------
# Detour generation
# ---------------------------------------------------------------------------


def test_a_detour_is_only_built_around_a_live_flag() -> None:
    """
    Chronic flags are not detour targets.

    The chronic layer covers most of Dhaka with 2 km radii, so "avoiding" one usually means
    avoiding the city — and the detour would be justified by a sentence that is technically
    true and practically useless.
    """
    assert worst_live_flag([flag(kind=IncidentKind.CHRONIC, severity_now=90.0)]) is None
    assert worst_live_flag([flag(kind=IncidentKind.FIRE, severity_now=60.0)]) is not None


def test_a_nearly_expired_flag_is_not_worth_a_detour() -> None:
    """Routing someone minutes out of their way to avoid a severity-8 flag is worse advice."""
    assert worst_live_flag([flag(severity_now=8.0)]) is None


def test_the_worst_live_flag_wins() -> None:
    worst = flag(severity_now=75.0, statement="Road blocked near Mirpur 10.")
    chosen = worst_live_flag([flag(severity_now=30.0), worst, flag(severity_now=45.0)])
    assert chosen is not None and chosen.severity_now == 75.0


def test_a_waypoint_is_offered_for_a_flag_sitting_on_the_route() -> None:
    """
    **The case the first implementation got wrong, and the commonest real one.**

    A flag on the road you are travelling. The original geometry pushed away from the flag
    *towards the nearest path vertex*, so when the flag sat on a vertex there was no
    direction at all and it returned nothing - meaning no detour was ever generated for an
    obstruction actually on the route, which is the only kind worth detouring around.

    Perpendicular to the route's heading always exists.
    """
    target = flag(lat=23.75, lon=90.40, radius_m=400)
    path = [(23.74, 90.40), (23.75, 90.40), (23.76, 90.40)]  # flag is ON a vertex

    waypoints = detour_waypoints(target, path, corridor_radius_m=150)

    assert len(waypoints) == 2, "one candidate either side of the road"
    for waypoint in waypoints:
        assert haversine_m(target.lat, target.lon, *waypoint) > 400 + 150


def test_the_two_waypoints_are_on_opposite_sides() -> None:
    """
    Which side has a usable road is not knowable here, so both are tried.

    On a north-south route they must differ in longitude, not latitude - a "sideways" step
    that went forwards along the route would clear nothing.
    """
    target = flag(lat=23.75, lon=90.40, radius_m=300)
    path = [(23.74, 90.40), (23.76, 90.40)]  # due north

    left, right = detour_waypoints(target, path, corridor_radius_m=150)

    assert (left[1] - target.lon) * (right[1] - target.lon) < 0, "not opposite sides"
    assert abs(left[0] - target.lat) < abs(left[1] - target.lon), "offset should be east-west"


def test_no_waypoint_without_a_line_to_be_perpendicular_to() -> None:
    """A coincidence, not an error - returns an empty list."""
    target = flag(lat=23.75, lon=90.40)
    assert detour_waypoints(target, [(23.75, 90.40)], corridor_radius_m=150) == []
    assert detour_waypoints(target, [], corridor_radius_m=150) == []
    assert detour_waypoints(target, [(23.75, 90.40), (23.75, 90.40)], corridor_radius_m=150) == []


# ---------------------------------------------------------------------------
# Explanations: S13, beat 4
# ---------------------------------------------------------------------------


def test_an_explanation_quotes_the_framed_statement() -> None:
    """
    `explain.py` assembles; it does not write. The statement must appear verbatim.

    If this fails because the text was rephrased, the fix is not to update the assertion —
    flag prose comes from `app/policy/framing.py` and nowhere else.
    """
    sentence = explain_route(
        [flag(statement="Road blocked near Bangshal.", source_count=3)],
        duration_s=600,
        fastest_duration_s=600,
    )
    assert "Road blocked near Bangshal" in sentence
    assert "three sources" in sentence


def test_an_unconfirmed_flag_is_labelled_in_the_explanation() -> None:
    sentence = explain_route(
        [flag(status="unconfirmed", source_count=1, confidence=0.6)],
        duration_s=600,
        fastest_duration_s=600,
    )
    assert "one source, unconfirmed" in sentence


def test_a_clean_route_says_so_rather_than_saying_nothing() -> None:
    """An empty explanation reads as a failure to load. "We checked" is a real answer."""
    sentence = explain_route([], duration_s=600, fastest_duration_s=600)
    assert "Nothing flagged" in sentence


def test_the_explanation_names_one_flag_and_counts_the_rest() -> None:
    """
    The concept document's target sentence names a single event.

    Two named flags plus a trade-off clause measured 186 characters, past what fits a route
    card — which is why this is 1 and why `MAX_EXPLANATION_LENGTH` exists.
    """
    sentence = explain_route(
        [flag(statement="Road blocked near Bangshal."), flag(), flag()],
        duration_s=600,
        fastest_duration_s=600,
    )
    assert "Bangshal" in sentence
    assert "2 other flagged locations" in sentence
    assert len(sentence) <= MAX_EXPLANATION_LENGTH


def test_the_trade_off_sentence_is_the_comparison_beat_4_asks_for() -> None:
    assert trade_off_sentence(duration_s=840, fastest_duration_s=600, avoided_count=2) == (
        "4 minutes longer, avoids 2 flagged corridors."
    )
    assert trade_off_sentence(duration_s=660, fastest_duration_s=600, avoided_count=1) == (
        "1 minute longer, avoids 1 flagged corridor."
    )


def test_no_trade_off_is_stated_when_there_is_nothing_to_trade() -> None:
    """The fastest route that avoids nothing extra needs no justification."""
    assert trade_off_sentence(duration_s=600, fastest_duration_s=600, avoided_count=0) is None


def test_an_explanation_cannot_carry_banned_vocabulary() -> None:
    """
    The guard runs on the finished string, not only the inputs.

    Concatenation is the one place a banned term could be assembled from individually safe
    parts, and this is the last point before the text reaches a screen.
    """
    with pytest.raises(FramingViolation):
        assert_explanation_safe("Passes a violent clash near Bangshal (three sources).")


def test_an_explanation_cannot_carry_a_url() -> None:
    with pytest.raises(FramingViolation):
        assert_explanation_safe("Passes road works, see https://example.test/x")


def test_an_over_long_explanation_is_refused_rather_than_truncated() -> None:
    """
    Truncating would cut a sentence mid-clause and could strand a negation.

    The error says to name fewer flags rather than to raise the limit, because the limit is
    the framing control `framing.py` describes: there is no room for narrative, and
    narrative is where characterisation creeps back in.
    """
    with pytest.raises(FramingViolation, match="Name fewer flags"):
        assert_explanation_safe("Road works. " * 40)


def test_the_explanation_limit_is_separate_from_the_flag_statement_limit() -> None:
    """
    Two different surfaces, two different budgets — and deliberately not one constant.

    160 is documented in `framing.py` as "one line on a map pin". An explanation quotes one
    of those and adds a source count and a trade-off clause, so it is structurally longer
    while containing nothing a reviewer has not already seen.
    """
    from app.policy.framing import MAX_STATEMENT_LENGTH

    assert MAX_EXPLANATION_LENGTH > MAX_STATEMENT_LENGTH
    assert MAX_EXPLANATION_LENGTH <= 260, "still a sentence, not a paragraph"


# ---------------------------------------------------------------------------
# S12's sprint-exit check: the ranking actually avoids the flag
# ---------------------------------------------------------------------------


async def test_the_top_route_avoids_a_flagged_corridor() -> None:
    """
    **S12's last bullet**: *"Integration test: seeded flag on a known corridor ⇒ top route
    avoids it."*

    Everything else in this file tests a part — the penalty, the combination, the duration
    axis, the filter. None of them would catch the one failure that matters most on stage:
    the parts all working and the **ranking** still putting the flagged route first. A sign
    error in `composite`, or sorting ascending, and every unit test here still passes while
    the app confidently recommends the fire.

    Two corridors, one flag, scored through the real scorer and ranked by the real
    composite. The clean one is slightly longer, so this also pins the trade-off: a modest
    detour to avoid a severe flag must win.
    """
    from app.routing.scorer import composite, score_path

    blocked_path = [(23.750, 90.400), (23.760, 90.400)]
    clear_path = [(23.750, 90.420), (23.762, 90.420)]  # parallel, a little longer

    obstruction = flag(
        severity_now=80.0,
        kind=IncidentKind.FIRE,
        lat=23.755,
        lon=90.400,
        radius_m=300,
        statement="Road blocked near Bangshal.",
    )

    # One surface, asked about two corridors. `_Surface` returns its flags for any path, so
    # the flag is placed on the blocked corridor by giving the clear corridor an empty one --
    # which is what `flags_near_path` would do for real, and is tested directly in
    # `test_distance_is_measured_to_the_segment_not_the_vertices`.
    blocked = await score_path(_Surface([obstruction]), path=blocked_path, at=NOW)
    clear = await score_path(_Surface([]), path=clear_path, at=NOW)

    fastest_s = 600.0
    ranked = sorted(
        [(blocked, 600.0), (clear, 780.0)],  # the clear route is 3 minutes longer
        key=lambda pair: composite(pair[0].safety_score, pair[1], fastest_s),
        reverse=True,
    )

    assert ranked[0][0] is clear, (
        "the top route must avoid the flagged corridor; a 3-minute detour around a "
        "severity-80 fire is the trade this product exists to make"
    )
    assert clear.safety_score == MAX_SAFETY
    assert blocked.safety_score < 50.0


async def test_a_trivial_flag_does_not_justify_a_long_detour() -> None:
    """
    The same machinery in the other direction, which is the half that is easy to lose.

    If any flag at all made a detour win, the product would send people the long way round
    for a lane closure — and a routing app that always returns the longest route stops being
    used. `ROUTE_SAFETY_WEIGHT` is what balances this, and this test is what notices when
    someone raises it to 0.95 to make a demo look better.
    """
    from app.routing.scorer import composite, score_path

    path = [(23.750, 90.400), (23.760, 90.400)]
    minor = await score_path(
        _Surface([flag(severity_now=12.0, kind=IncidentKind.CONSTRUCTION)]), path=path, at=NOW
    )
    clear = await score_path(_Surface([]), path=path, at=NOW)

    fastest_s = 600.0
    direct = composite(minor.safety_score, 600.0, fastest_s)
    long_way = composite(clear.safety_score, 1500.0, fastest_s)  # 15 min vs 10

    assert direct > long_way, (
        "a severity-12 flag should not justify a 150% detour; check ROUTE_SAFETY_WEIGHT"
    )


# ---------------------------------------------------------------------------
# Durations: two corrections, because the graph has no traffic data
# ---------------------------------------------------------------------------


def test_the_congestion_factor_is_a_correction_not_a_rounding() -> None:
    """
    OSRM answers "how long on an empty road", which is the only question the graph can
    answer: `car.lua` speeds come from `maxspeed` tags and road-class defaults.

    Measured on Bangshal -> Mirpur-10 (2026-10-09): **12.61 km in 13.8 min = 54.8 km/h**,
    median segment speed 56 km/h. That is not slightly optimistic across central Dhaka, it
    is physically absurd — and it matters beyond the label, because `composite` trades
    safety against time, so a wrong duration changes which route is *recommended*.

    The factor must therefore be a real correction. A value near 1.0 would mean someone
    had quietly decided free-flow was fine; a value near 0 would mean a journey time
    nobody believes either.
    """
    factor = settings.ROUTE_CONGESTION_FACTOR
    assert 0.15 <= factor <= 0.6, (
        f"ROUTE_CONGESTION_FACTOR={factor} is outside the range that produces a believable "
        "Dhaka duration. See its derivation in config.py before changing it."
    )

    free_flow_kmh = 54.8  # measured
    assert 10.0 <= free_flow_kmh * factor <= 30.0, (
        "the corrected average speed should land in a plausible Dhaka range"
    )


def test_the_congestion_factor_cannot_reorder_routes() -> None:
    """
    A uniform multiplier must not change which route wins.

    It is applied to every driving candidate equally, so the ranking is unaffected — but
    that is a property worth pinning, because the obvious "improvement" is to vary the
    factor by road class, and the moment it varies it starts deciding the recommendation
    on a number nobody has calibrated.
    """
    fastest_s = 600.0
    pairs = [(70.0, 600.0), (85.0, 900.0), (60.0, 660.0)]

    plain = sorted(pairs, key=lambda p: composite(p[0], p[1], fastest_s), reverse=True)
    factor = settings.ROUTE_CONGESTION_FACTOR
    scaled = sorted(
        pairs,
        key=lambda p: composite(p[0], p[1] / factor, fastest_s / factor),
        reverse=True,
    )

    assert [p[0] for p in plain] == [p[0] for p in scaled], (
        "scaling every duration by the same factor reordered the routes; composite's "
        "duration axis is supposed to be relative"
    )


def test_walking_is_not_given_the_traffic_correction() -> None:
    """
    Pedestrians do not sit in traffic.

    Walking durations are computed from distance at a walking pace instead, because OSRM
    answers a `/foot/` request from the car graph — it returned 7.03 km in 9 minutes, which
    is 47 km/h presented as a walk. Applying a congestion factor on top of that would be
    correcting the wrong thing twice.
    """
    from app.services.route_service import _ASSUMED_WALK_KMH

    assert 3.5 <= _ASSUMED_WALK_KMH <= 6.0, "an adult walking pace, not a jog or a stroll"

    distance_km = 7.03
    walk_minutes = distance_km / _ASSUMED_WALK_KMH * 60
    drive_minutes = (distance_km / (54.8 * settings.ROUTE_CONGESTION_FACTOR)) * 60
    assert walk_minutes > drive_minutes * 2, (
        "walking the same distance should take materially longer than driving it; if these "
        "are close, one of the two corrections is not being applied"
    )
