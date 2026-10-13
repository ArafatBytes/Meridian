"""
Turn-by-turn directions: where the road names come from, and what happens when
there are none.

Before this, the router asked OSRM for a geometry and nothing else, so the client
derived turns from the shape of the polyline — a reliable side and distance, and no
way to name a road. `steps=true` is what changed that.

The invariant worth protecting is **not** "every manoeuvre has a name". It is the
opposite: a great many Dhaka ways have no OSM `name` tag at all, several are tagged
in Bangla, and the straight-line fallback has no manoeuvres whatsoever. So every
layer has to carry an unnamed step without producing a broken instruction, and
these tests arrange exactly those cases.

`start_m` gets the most attention here because it is the only derived field. OSRM
gives each step a distance and no position, and the client needs to answer "which
manoeuvre am I approaching" from the single `alongM` figure it computes off the
polyline — so the backend accumulates the distances and scales them onto the
route's own total. Get the scaling wrong and the final `arrive` step sits past the
end of the line the client is walking, so it never becomes current and the banner
shows the second-to-last instruction all the way to the destination.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.invariant


def _payload(steps: list[dict], distance: float = 1000.0) -> dict:
    """An OSRM response carrying one route with one leg of `steps`."""
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": distance,
                "duration": 300.0,
                "geometry": {
                    "coordinates": [[90.39, 23.73], [90.40, 23.74], [90.41, 23.75]]
                },
                "legs": [{"steps": steps}],
            }
        ],
    }


def _step(**overrides) -> dict:
    step = {
        "name": "Mirpur Road",
        "distance": 250.0,
        "duration": 75.0,
        "maneuver": {"type": "turn", "modifier": "left", "location": [90.40, 23.74]},
    }
    step.update(overrides)
    return step


# ---------------------------------------------------------------------------
# The OSRM layer
# ---------------------------------------------------------------------------


def test_the_router_asks_for_steps() -> None:
    """
    Without `steps=true` in the query there are no manoeuvres to carry, and the
    client silently falls back to geometry for every route. That is a working app
    with worse directions, which is exactly the kind of regression nothing notices.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "app" / "routing" / "osrm.py").read_text(
        encoding="utf-8"
    )
    # Both request paths: the alternatives query and the single-route/detour query.
    assert source.count('"steps": "true"') == 2


def test_steps_are_parsed_with_coordinates_in_our_order() -> None:
    from app.routing.osrm import _parse

    routes = _parse(_payload([_step()]), "local")
    assert len(routes) == 1
    (step,) = routes[0].steps
    # OSRM speaks (lon, lat); everything above the parser speaks (lat, lon).
    assert step.lat == pytest.approx(23.74)
    assert step.lon == pytest.approx(90.40)
    assert step.name == "Mirpur Road"
    assert step.maneuver_type == "turn"
    assert step.modifier == "left"


def test_an_unnamed_way_yields_an_empty_name_not_none() -> None:
    """
    `""`, so every consumer can test it the same way. OSRM sends an explicit empty
    string for an unnamed way and `None` would make `if step.name` and
    `step.name == ""` disagree.
    """
    from app.routing.osrm import _parse

    (step,) = _parse(_payload([_step(name="")]), "local")[0].steps
    assert step.name == ""

    (step,) = _parse(_payload([_step(name=None)]), "local")[0].steps
    assert step.name == ""


def test_a_malformed_manoeuvre_is_skipped_rather_than_losing_the_route() -> None:
    """
    A route with slightly plainer directions beats no route. The client narrates
    from geometry when steps are missing, so dropping one is a graceful degradation
    and raising would not be.
    """
    from app.routing.osrm import _parse

    payload = _payload(
        [
            {"name": "A", "maneuver": {"type": "turn", "location": []}},  # no location
            _step(name="B"),
        ]
    )
    routes = _parse(payload, "local")
    assert [s.name for s in routes[0].steps] == ["B"]


def test_legs_are_flattened_so_a_detour_keeps_its_second_half() -> None:
    """
    The detour builder adds a via point, which gives OSRM two legs. Indexing
    `legs[0]` would quietly drop every manoeuvre after the via.
    """
    from app.routing.osrm import _parse

    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 20.0,
                "duration": 10.0,
                "geometry": {"coordinates": [[90.39, 23.73], [90.40, 23.74]]},
                "legs": [
                    {"steps": [_step(name="first")]},
                    {"steps": [_step(name="second")]},
                ],
            }
        ],
    }
    assert [s.name for s in _parse(payload, "local")[0].steps] == ["first", "second"]


def test_a_route_with_no_legs_parses_to_no_steps() -> None:
    from app.routing.osrm import _parse_steps

    assert _parse_steps({"distance": 1.0}) == ()
    assert _parse_steps({"legs": None}) == ()
    assert _parse_steps({"legs": [{"steps": None}]}) == ()


# ---------------------------------------------------------------------------
# `start_m`, the only derived field
# ---------------------------------------------------------------------------


def test_step_offsets_accumulate_from_the_route_start() -> None:
    from app.routing.osrm import OsrmRoute, OsrmStep
    from app.services.route_service import RouteService

    raw = OsrmRoute(
        path=[(23.73, 90.39), (23.75, 90.41)],
        distance_m=900.0,
        duration_s=300.0,
        engine="local",
        steps=tuple(
            OsrmStep(
                name=name,
                maneuver_type="turn",
                modifier="left",
                distance_m=distance,
                duration_s=60.0,
                lat=23.74,
                lon=90.40,
            )
            for name, distance in (("a", 300.0), ("b", 300.0), ("c", 300.0))
        ),
    )
    steps = RouteService._to_route_steps(raw)
    assert [s.start_m for s in steps] == [0.0, 300.0, 600.0]


def test_the_last_step_lands_at_the_route_distance_not_past_it() -> None:
    """
    The scaling, and the reason it exists. OSRM rounds the route distance and each
    step distance independently, so they disagree by a few metres -- and the client
    measures its own progress against the polyline, a third number again.

    Unscaled, the final `arrive` step sits beyond the end of the line being walked,
    never becomes the current step, and the banner shows the previous instruction
    all the way to the destination.
    """
    from app.routing.osrm import OsrmRoute, OsrmStep
    from app.services.route_service import RouteService

    # Steps sum to 1003 m; the route says 1000 m. A realistic rounding gap.
    distances = [120.4, 310.2, 455.9, 116.5]
    raw = OsrmRoute(
        path=[(23.73, 90.39), (23.75, 90.41)],
        distance_m=1000.0,
        duration_s=300.0,
        engine="local",
        steps=tuple(
            OsrmStep(
                name="",
                maneuver_type="turn",
                modifier="left",
                distance_m=d,
                duration_s=30.0,
                lat=23.74,
                lon=90.40,
            )
            for d in distances
        ),
    )
    steps = RouteService._to_route_steps(raw)
    end = steps[-1].start_m + steps[-1].distance_m
    assert end == pytest.approx(1000.0, abs=0.5)


def test_a_gross_mismatch_is_not_scaled() -> None:
    """
    A ratio far from 1 means these steps do not describe this geometry, and
    stretching them to fit would produce confidently wrong offsets. Better to leave
    them alone: the client's step matching then drifts, which is visible, rather
    than being subtly wrong everywhere.
    """
    from app.routing.osrm import OsrmRoute, OsrmStep
    from app.services.route_service import RouteService

    raw = OsrmRoute(
        path=[(23.73, 90.39), (23.75, 90.41)],
        distance_m=4000.0,
        duration_s=300.0,
        engine="local",
        steps=(
            OsrmStep(
                name="",
                maneuver_type="turn",
                modifier="left",
                distance_m=500.0,
                duration_s=60.0,
                lat=23.74,
                lon=90.40,
            ),
        ),
    )
    (step,) = RouteService._to_route_steps(raw)
    assert step.distance_m == pytest.approx(500.0)


def test_a_route_with_no_steps_maps_to_an_empty_list() -> None:
    """
    The straight-line fallback. It is not a road route and has no manoeuvres, and
    the client treats an empty list as "narrate from the geometry instead" -- which
    is what it did before any of this existed.
    """
    from app.routing.osrm import OsrmRoute
    from app.services.route_service import RouteService

    raw = OsrmRoute(
        path=[(23.73, 90.39), (23.75, 90.41)],
        distance_m=1000.0,
        duration_s=300.0,
        engine="straight-line",
    )
    assert RouteService._to_route_steps(raw) == []


# ---------------------------------------------------------------------------
# Framing: a road's name is not a characterisation
# ---------------------------------------------------------------------------


def test_step_names_do_not_go_through_the_mobility_framing_guard() -> None:
    """
    `policy/framing.py` exists to stop the product characterising a *place*, and its
    banned list includes `jatiya`, `awami` and `political` -- all of which appear in
    ordinary Dhaka road names. A road's name is a fact about the road, published by
    OSM; it is not this product's claim about anywhere.

    Running it through a vocabulary guard built for a different purpose would
    silently drop real street names and leave the user with worse directions. This
    test pins that decision so it is a deliberate choice rather than an oversight
    someone later "fixes".
    """
    from app.policy.framing import find_banned_terms
    from app.routing.osrm import _parse

    # A real-shaped name that the mobility guard would reject.
    name = "Jatiya Sangsad Bhaban Road"
    assert find_banned_terms(name), "this test is pointless if the guard would allow it"

    (step,) = _parse(_payload([_step(name=name)]), "local")[0].steps
    assert step.name == name


def test_the_mobility_statement_is_still_guarded() -> None:
    """
    The exemption above is for step names only. A flag's own statement is the
    product's claim and goes through the guard exactly as before.
    """
    from app.policy.framing import FramingViolation, assert_mobility_safe

    with pytest.raises(FramingViolation):
        assert_mobility_safe("Dangerous area near Jatiya Sangsad.")
