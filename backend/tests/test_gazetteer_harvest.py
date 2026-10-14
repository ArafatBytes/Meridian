"""
The harvest's judgment calls, tested without touching the network.

`scripts/harvest_gazetteer.py` decides three things that the gazetteer's
correctness rests on, and all three are pure functions of the harvested rows:

  * what a repeated name means — one place in two layers, or two places;
  * what a road is, given that OSM delivers one road as fifty short ways and
    this gazetteer stores a point with a radius;
  * which names are too generic to identify anything.

S31 added the road and bus-stop layers, and each of those brought a failure mode
that did not exist when the harvest only asked for places and junctions. The
tests below are the ones that would have caught them.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

harvest = importlib.import_module("harvest_gazetteer")

# 0.001 degrees of longitude is about 102 m at Dhaka's latitude. Spacings below
# are written in degrees and the comments give the metres.
LAT = 23.78
LON = 90.40


def row(
    name: str,
    kind: str,
    lat: float,
    lon: float,
    *,
    osm_id: int = 0,
    bangla: str = "",
    radius: int | None = None,
) -> dict[str, Any]:
    """A harvested row, in the shape `build` makes them."""
    return {
        "id": f"osm-way-{osm_id or abs(hash((name, lat, lon))) % 10**9}",
        "name_bn": bangla,
        "name_en": name,
        "aliases": [],
        "kind": kind,
        "lat": lat,
        "lon": lon,
        "radius_m": radius if radius is not None else harvest.DEFAULT_RADIUS_M.get(kind, 300),
        "source": "osm:test",
        "reviewed": False,
        "ambiguous": False,
    }


def segments(name: str, count: int, *, step: float, start: float = LON) -> list[dict[str, Any]]:
    """`count` ways of one road, strung out along a line of latitude."""
    return [
        row(name, "road", LAT, round(start + index * step, 6), osm_id=1000 + index)
        for index in range(count)
    ]


# ---------------------------------------------------------------------------
# Roads: a line stored as a point
# ---------------------------------------------------------------------------


def test_one_road_becomes_one_entry_not_fifty() -> None:
    """
    OSM breaks a road at every junction. Without clustering, Satmasjid Road
    arrives as dozens of entries with identical names a few hundred metres
    apart, which `resolve_collisions` would then read as a name belonging to
    dozens of places and refuse outright.
    """
    roads = harvest.cluster_roads(segments("Satmasjid Road", 12, step=0.005))
    assert len(roads) == 1
    assert roads[0]["segments"] == 12


def test_a_road_entry_sits_in_the_middle_of_its_own_segments() -> None:
    roads = harvest.cluster_roads(segments("Satmasjid Road", 11, step=0.005))
    middle = LON + 5 * 0.005
    assert roads[0]["lon"] == pytest.approx(middle, abs=1e-4)
    assert roads[0]["lat"] == pytest.approx(LAT, abs=1e-6)


def test_a_road_radius_is_measured_not_defaulted() -> None:
    """
    Every other kind takes a radius from `DEFAULT_RADIUS_M`. A road cannot: a
    200 m lane and a 3 km arterial are the same kind and are not the same claim.
    """
    short = harvest.cluster_roads(segments("Short Lane", 3, step=0.002))[0]
    longer = harvest.cluster_roads(segments("Longer Road", 14, step=0.005))[0]
    assert short["radius_m"] < longer["radius_m"]
    assert "road" not in harvest.DEFAULT_RADIUS_M


def test_a_road_radius_stays_inside_its_clamp() -> None:
    for count, step in ((2, 0.0005), (8, 0.005), (30, 0.005)):
        entry = harvest.cluster_roads(segments("Some Road", count, step=step))[0]
        assert harvest.ROAD_MIN_RADIUS_M <= entry["radius_m"] <= harvest.ROAD_MAX_RADIUS_M


def test_an_arterial_too_long_to_pin_is_refused_rather_than_pinned_at_its_middle() -> None:
    """
    Mirpur Road is about 8 km. "An incident on Mirpur Road" narrows it to a
    tenth of the city, and a pin at the midpoint would be up to 4 km from the
    event — the wrong-pin failure the discard invariant exists to prevent. The
    entry is kept, so the query never reaches the LLM tier, and marked ambiguous
    so the loader declines it.
    """
    # 20 segments, 508 m apart: about 9.7 km end to end.
    entry = harvest.cluster_roads(segments("Mirpur Road", 20, step=0.005))[0]
    assert entry["span_m"] > 2 * harvest.ROAD_REFUSE_HALF_SPAN_M
    assert entry["ambiguous"] is True


def test_a_road_short_enough_to_pin_is_not_refused() -> None:
    """The other direction. Refusing everything would be safe and useless."""
    # 6 segments, 508 m apart: about 2.5 km, the length of Satmasjid Road.
    entry = harvest.cluster_roads(segments("Satmasjid Road", 6, step=0.005))[0]
    assert entry["ambiguous"] is False
    assert entry["radius_m"] <= harvest.ROAD_MAX_RADIUS_M


def test_the_same_road_name_in_two_neighbourhoods_stays_two_entries() -> None:
    """
    Dhaka has "Road No 5" in a dozen places. Chaining them into one entry would
    put its centroid between them, somewhere neither road is.
    """
    here = segments("Road No 5", 4, step=0.002)
    there = [
        row("Road No 5", "road", LAT + 0.05, LON + index * 0.002, osm_id=2000 + index)
        for index in range(4)
    ]  # 0.05 degrees of latitude is about 5.5 km
    roads = harvest.cluster_roads([*here, *there])
    assert len(roads) == 2

    # And the ambiguity machinery then refuses the name, which is the point.
    resolved = harvest.resolve_collisions(roads)
    assert all(entry["ambiguous"] for entry in resolved)


def test_a_road_cluster_keeps_the_lowest_osm_id_so_aliases_survive_a_reharvest() -> None:
    """
    `aliases.json` is keyed by entry id. If a re-harvest picked a different
    segment of the same road as the seed, every hand-written alias on that road
    would silently stop working — which is why the script refuses to write a
    file that has orphaned an annotated id.
    """
    forwards = harvest.cluster_roads(segments("Stable Road", 9, step=0.004))
    backwards = harvest.cluster_roads(list(reversed(segments("Stable Road", 9, step=0.004))))
    assert forwards[0]["id"] == backwards[0]["id"]


# ---------------------------------------------------------------------------
# Borrowed names
# ---------------------------------------------------------------------------


def test_a_bus_stop_named_after_a_neighbourhood_does_not_erase_the_neighbourhood() -> None:
    """
    The regression S31's own new layer would have caused.

    OSM names Dhaka's bus stops after the areas they serve — plain "Mohakhali",
    not "Mohakhali Bus Stop" — and the stop node sits well over `MERGE_RADIUS_M`
    from the area's label node. Left alone, `resolve_collisions` reads that as
    two different places sharing a name and marks both ambiguous, so adding the
    vernacular layer would have *removed* Mohakhali from the gazetteer.
    """
    area = row("Mohakhali", "area", LAT, LON, osm_id=1)
    stop = row("Mohakhali", "stop", LAT, LON + 0.02, osm_id=2)  # about 2 km away

    kept = harvest.resolve_collisions(
        harvest._drop_borrowed_names([area, stop], frozenset())
    )

    survivors = {entry["id"]: entry for entry in kept}
    assert area["id"] in survivors, "the area must survive"
    assert survivors[area["id"]]["ambiguous"] is False, (
        "a borrowed name must not make the place it was borrowed from ambiguous"
    )


def test_without_the_borrowed_name_rule_the_place_would_have_been_refused() -> None:
    """
    The tripwire for the test above: prove the rule is doing the work, rather
    than the outcome being true for some other reason.
    """
    area = row("Mohakhali", "area", LAT, LON, osm_id=1)
    stop = row("Mohakhali", "stop", LAT, LON + 0.02, osm_id=2)
    kept = harvest.resolve_collisions([area, stop])  # rule skipped on purpose
    assert all(entry["ambiguous"] for entry in kept)


def test_a_borrower_with_a_name_of_its_own_keeps_it() -> None:
    area = row("Mohakhali", "area", LAT, LON, osm_id=1)
    stop = row("Mohakhali", "stop", LAT, LON + 0.02, osm_id=2, bangla="মহাখালী বাস স্টপ")
    kept = harvest._drop_borrowed_names([area, stop], frozenset())
    survivor = next(entry for entry in kept if entry["id"] == stop["id"])
    assert survivor["name_en"] == "", "the borrowed name goes"
    assert survivor["name_bn"] == "মহাখালী বাস স্টপ", "its own name stays"


def test_two_genuinely_different_places_are_still_refused() -> None:
    """
    The rule must not become a way to resolve a real ambiguity. Two `place`
    nodes 10 km apart sharing a name is Uttara's and Bashundhara's Sector 11,
    and neither of them borrowed the name from the other.
    """
    uttara = row("Sector 11", "neighbourhood", 23.87, 90.39, osm_id=1)
    bashundhara = row("Sector 11", "neighbourhood", 23.81, 90.43, osm_id=2)
    kept = harvest.resolve_collisions(
        harvest._drop_borrowed_names([uttara, bashundhara], frozenset())
    )
    assert all(entry["ambiguous"] for entry in kept)


def test_an_annotated_entry_is_never_stripped_of_its_name() -> None:
    """A person wrote aliases for this id. The script does not overrule them."""
    area = row("Farmgate", "area", LAT, LON, osm_id=1)
    stop = row("Farmgate", "stop", LAT, LON + 0.02, osm_id=2)
    kept = harvest._drop_borrowed_names([area, stop], frozenset({stop["id"]}))
    survivor = next(entry for entry in kept if entry["id"] == stop["id"])
    assert survivor["name_en"] == "Farmgate"


# ---------------------------------------------------------------------------
# Merging
# ---------------------------------------------------------------------------


def test_merging_keeps_the_widest_radius_not_the_narrowest() -> None:
    """
    OSM lists Farmgate as both an area and a bus terminal 276 m apart. The
    terminal is the more specific point, so it is the record kept — but the area
    is the honest extent of what "Farmgate" means, and keeping the terminal's
    300 m would shrink the Farmgate area to the Farmgate bus bay.
    """
    area = row("Farmgate", "area", LAT, LON, osm_id=1)
    terminal = row("Farmgate", "terminal", LAT, LON + 0.002, osm_id=2)
    kept = harvest.resolve_collisions([area, terminal])
    assert len(kept) == 1
    assert kept[0]["kind"] == "terminal", "the specific point wins"
    assert kept[0]["radius_m"] == area["radius_m"], "the wide extent wins"


def test_a_hand_annotated_entry_wins_the_merge() -> None:
    """
    `aliases.json` is keyed by entry id, so a merge that dropped the annotated
    record would orphan a person's work — and the demo types one of those
    aliases on stage.
    """
    annotated = row("Gabtoli", "area", LAT, LON, osm_id=1)
    other = row("Gabtoli", "terminal", LAT, LON + 0.002, osm_id=2)
    kept = harvest.resolve_collisions([annotated, other], frozenset({annotated["id"]}))
    assert len(kept) == 1
    assert kept[0]["id"] == annotated["id"], (
        "the annotated record must survive even though `terminal` is more specific"
    )


def test_a_merge_keeps_the_other_records_spellings_as_aliases() -> None:
    area = row("Farmgate", "area", LAT, LON, osm_id=1, bangla="ফার্মগেট")
    terminal = row("Farmgate", "terminal", LAT, LON + 0.002, osm_id=2, bangla="ফার্মগেইট")
    kept = harvest.resolve_collisions([area, terminal])
    assert "ফার্মগেট" in kept[0]["aliases"] or "ফার্মগেইট" in kept[0]["aliases"]


# ---------------------------------------------------------------------------
# Generic names
# ---------------------------------------------------------------------------


def test_a_bangla_only_generic_name_is_dropped() -> None:
    """
    The bug the old check had. It tested the romanised name and only when there
    was no Bangla name at all, so a node whose entire name was "মসজিদ" was kept
    — and with the new layers there are hundreds of those.
    """
    assert harvest.is_junk("মসজিদ", "") is True
    assert harvest.is_junk("বাজার", "") is True
    assert harvest.is_junk("থানা", "") is True


def test_a_generic_name_in_both_scripts_is_dropped() -> None:
    assert harvest.is_junk("মসজিদ", "Mosque") is True


def test_a_real_place_that_contains_a_generic_word_is_kept() -> None:
    """
    The filter is on the whole name, never a substring. "Karwan Bazar" is a
    place; "Bazar" is not.
    """
    for bangla, latin in (
        ("কারওয়ান বাজার", "Karwan Bazar"),
        ("", "Satmasjid Road"),
        ("সাতমসজিদ রোড", ""),
        ("", "Hazaribagh Police Station"),
        ("নিউ মার্কেট", "New Market"),
    ):
        assert harvest.is_junk(bangla, latin) is False, f"{latin or bangla!r} was dropped"


def test_a_feature_with_one_real_name_and_one_generic_name_is_kept() -> None:
    """Dropping it would lose the real name along with the useless one."""
    assert harvest.is_junk("মসজিদ", "Baitul Mukarram") is False


def test_a_nameless_feature_is_not_called_junk() -> None:
    """`build` filters those out earlier, on a different ground. Keep the two
    decisions separate so neither silently covers for the other."""
    assert harvest.is_junk("", "") is False


# ---------------------------------------------------------------------------
# The configuration has to be complete
# ---------------------------------------------------------------------------


def test_every_harvested_kind_has_a_radius_and_a_specificity() -> None:
    """
    Adding a layer means adding it in three places. A missing radius silently
    becomes 300 m and a missing specificity silently sorts last, and both of
    those are judgment calls nobody made.
    """
    kinds = {h.kind for h in harvest.HARVESTS}
    missing_radius = kinds - set(harvest.DEFAULT_RADIUS_M) - {"road"}
    missing_specificity = kinds - set(harvest.KIND_SPECIFICITY)
    assert not missing_radius, f"no DEFAULT_RADIUS_M for {missing_radius}"
    assert not missing_specificity, f"no KIND_SPECIFICITY for {missing_specificity}"


def test_every_kind_is_classed_as_naming_or_borrowing() -> None:
    kinds = {h.kind for h in harvest.HARVESTS}
    unclassed = kinds - harvest.NAMING_KINDS - harvest.BORROWING_KINDS
    assert not unclassed, f"{unclassed} is neither a naming nor a borrowing kind"
    assert not (harvest.NAMING_KINDS & harvest.BORROWING_KINDS)


def test_a_borrowing_kind_is_never_more_specific_than_a_naming_kind_it_shadows() -> None:
    """
    `stop` has the smallest radius in the file, so "most specific wins" would
    make a bus stop beat the neighbourhood it is named after on every merge.
    Specificity is about which point to trust, not which radius is smallest.
    """
    assert harvest.KIND_SPECIFICITY["stop"] > harvest.KIND_SPECIFICITY["neighbourhood"]
    assert harvest.KIND_SPECIFICITY["stop"] > harvest.KIND_SPECIFICITY["area"]
    assert harvest.KIND_SPECIFICITY["road"] > harvest.KIND_SPECIFICITY["neighbourhood"]


def test_the_cache_key_of_every_layer_is_unique() -> None:
    keys = [h.key for h in harvest.HARVESTS]
    assert len(keys) == len(set(keys)), "two layers would overwrite each other's cache"


def test_tiling_covers_the_whole_box_and_nothing_outside_it() -> None:
    for tiles in (1, 2, 3):
        boxes = harvest.tile_boxes(tiles)
        assert len(boxes) == tiles * tiles
        assert min(b[0] for b in boxes) == pytest.approx(harvest.BBOX_S)
        assert min(b[1] for b in boxes) == pytest.approx(harvest.BBOX_W)
        assert max(b[2] for b in boxes) == pytest.approx(harvest.BBOX_N)
        assert max(b[3] for b in boxes) == pytest.approx(harvest.BBOX_E)


def test_the_harvest_box_and_the_loader_box_have_not_drifted() -> None:
    """
    Two files carry the same four numbers. If they drift, the harvest writes
    entries the loader considers out of area, or stops filling part of the zone
    the LLM gate still accepts answers in — and neither failure is visible
    except as places quietly not resolving.
    """
    from app.geo import gazetteer as loader

    assert (harvest.BBOX_S, harvest.BBOX_W, harvest.BBOX_N, harvest.BBOX_E) == (
        loader.BBOX_S,
        loader.BBOX_W,
        loader.BBOX_N,
        loader.BBOX_E,
    ), "scripts/harvest_gazetteer.py and app/geo/gazetteer.py disagree about the pilot box"


def test_the_readme_the_harvest_writes_still_carries_the_osm_licence() -> None:
    """ODbL requires attribution, and `_README` is the kind of block a tidy-up deletes."""
    blob = " ".join(str(value) for value in harvest.README.values()).lower()
    assert "openstreetmap" in blob
    assert "odbl" in blob


def test_the_bridge_layer_does_not_ask_for_every_named_way_that_crosses_water() -> None:
    """
    `way["bridge"]["name"]` matches every road way with a bridge on it and
    returns the *road's* name, so the bridge layer would fill up with short
    duplicate segments of roads `road_major` already has.
    """
    bridge = next(h for h in harvest.HARVESTS if h.key == "bridge")
    for selector in bridge.selectors:
        assert '["bridge"]["name"]' not in selector or "name" in selector.split('["bridge"]')[1], (
            f"{selector} is an unrestricted bridge query"
        )
    assert any("man_made" in selector for selector in bridge.selectors)
    assert any(re.search(r'\["name"~', selector) for selector in bridge.selectors)
