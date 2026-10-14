"""
Invariant: **unresolvable locations are discarded, never guessed.**

Concept document §12, IMPLEMENTATION_PLAN.md §4. A wrong pin is worse than no
pin: it sends somebody down a road on a claim nobody made. The plan expects a
judge to test this by typing a place that does not exist.

These tests touch no network. The LLM tier is exercised with `allow_llm=False` or
a stubbed client, because an invariant test that depends on a free-tier daily
quota is an invariant test that fails for the wrong reason.

The cases here are not hypothetical. Each one is a bug this code actually had:

* `Sector 11` resolved to `Sector 10` at 0.89 confidence, because the two names
  are 89% similar as strings while being different places 2 km apart.
* `Farmgate` was *refused* because OpenStreetMap lists it in two layers 276 m
  apart and the duplicate check ignored distance — the invariant failing in the
  other direction, which costs a real place.
"""

import asyncio
from pathlib import Path

import pytest

from app.geo import gazetteer as gaz
from app.geo.agent import resolve_place
from app.geo.gazetteer import GazetteerError, gazetteer, in_pilot_box, load, normalise, numbers

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
GAZETTEER = BACKEND / "data" / "gazetteer" / "dhaka_central.json"
ALIASES = BACKEND / "data" / "gazetteer" / "aliases.json"

# A place-shaped string the gazetteer does not hold and should never hold, used
# wherever a test needs "we have never heard of this" as distinct from "we refuse
# this on purpose". It is named once because picking a real-but-absent place
# instead ties the test to the data: two tests used "Hatirjheel" on exactly that
# reasoning and both broke the day S31 harvested it.
UNKNOWN_PLACE = "Kolabagan Antarctic Research Station"


# ---------------------------------------------------------------------------
# The data file itself
# ---------------------------------------------------------------------------


def test_the_gazetteer_file_exists_and_loads() -> None:
    assert GAZETTEER.is_file(), (
        f"{GAZETTEER} is missing. Run `python backend/scripts/harvest_gazetteer.py`."
    )
    assert len(load(GAZETTEER, ALIASES)) > 0


def test_the_pilot_zone_has_at_least_the_150_entries_d03_promised() -> None:
    assert len(load(GAZETTEER, ALIASES)) >= 150


def test_every_entry_is_inside_the_pilot_box() -> None:
    """An entry outside the zone we claim to cover cannot be right."""
    strays = [e.id for e in load(GAZETTEER, ALIASES).entries if not in_pilot_box(e.lat, e.lon)]
    assert not strays, f"entries outside the pilot bbox: {strays[:5]}"


def test_every_entry_has_a_name_a_radius_and_a_source() -> None:
    bad: list[str] = []
    for entry in load(GAZETTEER, ALIASES).entries:
        if not (entry.name_bn or entry.name_en):
            bad.append(f"{entry.id}: no name in either script")
        if entry.radius_m <= 0:
            bad.append(f"{entry.id}: radius_m={entry.radius_m}")
        if not entry.source:
            bad.append(f"{entry.id}: no provenance")
    assert not bad, bad[:5]


def test_the_osm_attribution_survives() -> None:
    """
    ODbL requires it, and it is the kind of line that gets deleted during a tidy-up.
    """
    import json

    readme = json.loads(GAZETTEER.read_text(encoding="utf-8")).get("_README", {})
    blob = " ".join(str(v) for v in readme.values()).lower()
    assert "openstreetmap" in blob and "odbl" in blob, (
        "the gazetteer is OpenStreetMap data under ODbL; attribution must stay in _README"
    )


# ---------------------------------------------------------------------------
# Matching refuses rather than guesses
# ---------------------------------------------------------------------------


def test_a_place_that_does_not_exist_is_not_matched() -> None:
    g = load(GAZETTEER, ALIASES)
    for nonsense in (
        UNKNOWN_PLACE,
        "zzzzzzqqqq",
        "Mirpur 9999 golchattar",
        "the eiffel tower",
    ):
        assert g.resolve(nonsense) is None, f"{nonsense!r} should not have matched"


def test_numbers_are_identity_not_spelling() -> None:
    """
    `Sector 11` must never resolve to `Sector 10`.

    This is the regression test for a real wrong-pin bug: the two strings are 0.89
    similar, which cleared the fuzzy floor, and the places are 2 km apart.
    """
    g = load(GAZETTEER, ALIASES)
    for query, forbidden in (
        ("Sector 11", "Sector 10"),
        ("Sector 10", "Sector 11"),
        ("Mirpur 11", "Mirpur 10"),
        ("Mirpur 10", "Mirpur 11"),
    ):
        hit = g.resolve(query)
        if hit is None:
            continue  # refusing is always an acceptable answer here
        assert normalise(forbidden) not in normalise(hit.entry.display_name), (
            f"{query!r} resolved to {hit.entry.display_name!r}, which is a different place"
        )


def test_the_digit_guard_folds_scripts_but_not_values() -> None:
    assert numbers("মিরপুর ১০") == numbers("Mirpur 10") == ("10",)
    assert numbers("Sector 11") != numbers("Sector 10")


def test_an_ambiguous_name_is_refused_rather_than_picked() -> None:
    """
    Dhaka has more than one "Sector 11". Picking either would be a 10 km error.
    """
    g = load(GAZETTEER, ALIASES)
    ambiguous = [e for e in g.entries if e.ambiguous]
    assert ambiguous, "the harvest found no ambiguous names at all — the check is probably broken"
    for entry in ambiguous[:25]:
        for name in entry.all_names():
            hit = g.resolve(name)
            assert hit is None or hit.entry.id != entry.id, (
                f"{name!r} is ambiguous but resolved to {entry.id}"
            )


def test_well_known_landmarks_are_not_refused() -> None:
    """
    The invariant failing in the *other* direction still loses the demo.

    Before `resolve_collisions` compared distances, every one of these was marked
    ambiguous and refused, because OSM lists them in two layers a few hundred
    metres apart.
    """
    g = load(GAZETTEER, ALIASES)
    for name in ("Farmgate", "Motijheel", "Shapla Square", "Gulistan", "Dhanmondi", "Uttara"):
        assert g.resolve(name) is not None, f"{name!r} should resolve and does not"


def test_the_demo_phrase_resolves_in_both_scripts() -> None:
    """
    DEMO_PLAN.md §2 beat 3 commits to typing this on stage. OSM spells that
    roundabout গোলচক্কর; the demo says গোলচত্বর. Only `aliases.json` bridges that.
    """
    g = load(GAZETTEER, ALIASES)
    for phrase in ("Mirpur 10 golchattar", "মিরপুর ১০ গোলচত্বর", "Jatrabari chourasta"):
        hit = g.resolve(phrase)
        assert hit is not None, f"{phrase!r} does not resolve — check data/gazetteer/aliases.json"
        assert in_pilot_box(hit.entry.lat, hit.entry.lon)


# ---------------------------------------------------------------------------
# The agent's three outcomes, and only three
# ---------------------------------------------------------------------------


def test_the_agent_returns_unresolved_without_the_llm_rather_than_guessing() -> None:
    result = asyncio.run(resolve_place(UNKNOWN_PLACE, allow_llm=False))
    assert result.method == "unresolved"
    assert result.confidence == 0.0


def test_a_gazetteer_hit_reports_method_gazetteer() -> None:
    result = asyncio.run(resolve_place("Mirpur 10 golchattar", allow_llm=False))
    assert result.method == "gazetteer"
    assert in_pilot_box(result.lat, result.lon)


def test_an_llm_answer_outside_the_pilot_box_is_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The bounding-box gate. `openai/gpt-oss-120b` put Sayedabad 12.6 km out while
    reporting 0.78, so a model's own confidence cannot be the only guard.
    """
    from app.llm.models import GeoGuess

    async def paris(*_args: object, **_kwargs: object) -> GeoGuess:
        return GeoGuess(resolved=True, lat=48.8584, lon=2.2945, confidence=0.99)

    monkeypatch.setattr("app.geo.agent.complete", paris)
    result = asyncio.run(resolve_place("somewhere not in the gazetteer at all xyzzy"))
    assert result.method == "unresolved", "an answer outside Dhaka must be discarded"


def test_an_llm_refusal_becomes_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.llm.models import GeoGuess

    async def decline(*_args: object, **_kwargs: object) -> GeoGuess:
        return GeoGuess(resolved=False, lat=None, lon=None, confidence=0.0)

    monkeypatch.setattr("app.geo.agent.complete", decline)
    result = asyncio.run(resolve_place("zzzz not a place zzzz"))
    assert result.method == "unresolved"


def test_an_llm_answer_is_never_as_confident_as_a_gazetteer_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A model reported 0.95 on a fabrication. Its self-reported confidence is capped
    so it cannot outrank a verified entry downstream.
    """
    from app.geo.agent import LLM_CONFIDENCE_CEILING
    from app.llm.models import GeoGuess

    async def overconfident(*_args: object, **_kwargs: object) -> GeoGuess:
        return GeoGuess(resolved=True, lat=23.78, lon=90.40, confidence=1.0)

    monkeypatch.setattr("app.geo.agent.complete", overconfident)
    result = asyncio.run(resolve_place("xyzzy place not in the gazetteer"))
    assert result.method == "llm_gazetteer"
    assert result.confidence <= LLM_CONFIDENCE_CEILING < 1.0


def test_the_llm_tier_is_skipped_when_the_caller_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bulk ingestion must be able to resolve without spending a daily quota."""
    called = False

    async def tripwire(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("the LLM tier ran with allow_llm=False")

    monkeypatch.setattr("app.geo.agent.complete", tripwire)
    result = asyncio.run(resolve_place("definitely not in the gazetteer xyzzy", allow_llm=False))
    assert result.method == "unresolved"
    assert not called


def test_an_overlong_query_is_refused_before_spending_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    async def tripwire(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a sentence should never reach the model")

    monkeypatch.setattr("app.geo.agent.complete", tripwire)
    result = asyncio.run(resolve_place("x" * 500))
    assert result.method == "unresolved"


def test_a_broken_gazetteer_file_raises_rather_than_resolving_wrongly(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"entries": [{"id": "x"}]}', encoding="utf-8")
    with pytest.raises(GazetteerError):
        load(bad, ALIASES)


def test_the_cache_is_resettable() -> None:
    """`reset_cache` exists so tests and a dev re-harvest do not see stale data."""
    first = gazetteer()
    gaz.reset_cache()
    assert gazetteer() is not first


# ---------------------------------------------------------------------------
# A refusal for ambiguity outranks the LLM tier
# ---------------------------------------------------------------------------


def test_an_ambiguity_refusal_is_not_overturned_by_the_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The gazetteer knows "Sector 11" is two places 10 km apart. The model does not,
    and will confidently pick one. Our stronger tier must win.

    This is a regression test: the eval set recorded `Sector 11` as FABRICATED
    because the LLM answered Uttara's after the gazetteer had correctly declined.
    """
    from app.llm.models import GeoGuess

    called = False

    async def eager(*_args: object, **_kwargs: object) -> GeoGuess:
        nonlocal called
        called = True
        return GeoGuess(resolved=True, lat=23.8732, lon=90.3959, confidence=0.9)

    monkeypatch.setattr("app.geo.agent.complete", eager)
    result = asyncio.run(resolve_place("Sector 11"))
    assert result.method == "unresolved", "an ambiguous name must stay unresolved"
    assert not called, "the LLM must not even be asked about a name we refuse on purpose"


def test_an_unknown_name_still_reaches_the_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Guards the test above from over-reaching: "we have never heard of this" and
    "we refuse this on purpose" must stay different, or the LLM tier is dead code.
    """
    from app.llm.models import GeoGuess

    called = False

    async def answer(*_args: object, **_kwargs: object) -> GeoGuess:
        nonlocal called
        called = True
        return GeoGuess(resolved=True, lat=23.7556, lon=90.4042, confidence=0.8)

    monkeypatch.setattr("app.geo.agent.complete", answer)
    # This used to be "Hatirjheel", chosen because the gazetteer did not hold it.
    # S31's water layer does hold it, so the example had to change — the test is
    # about a name that is absent, and which name that is depends on the data.
    # `UNKNOWN_PLACE` is also asserted absent by
    # `test_a_place_that_does_not_exist_is_not_matched`, so the two cannot drift
    # apart silently.
    result = asyncio.run(resolve_place(UNKNOWN_PLACE))
    assert called, "a name the gazetteer simply lacks must still reach the LLM tier"
    assert result.method == "llm_gazetteer"


def test_the_gazetteer_distinguishes_refusal_from_ignorance() -> None:
    g = load(GAZETTEER, ALIASES)
    assert g.matches_ambiguous_only("Sector 11") is True
    assert g.matches_ambiguous_only(UNKNOWN_PLACE) is False
    assert g.matches_ambiguous_only("zzzzqqqq") is False


def test_no_hand_written_alias_collides_with_another_entrys_name() -> None:
    """
    An alias that duplicates a different entry's own name makes the query
    ambiguous, so the alias turns a working lookup into a refusal. Three of these
    were created and caught while writing aliases.json — গাবতলী, কাপ্তান বাজার and
    Nilkhet — each of which silently broke the lookup it was meant to help.
    """
    import json

    entries = load(GAZETTEER, ALIASES).entries
    owners: dict[str, set[str]] = {}
    for entry in entries:
        for own in (entry.name_bn, entry.name_en):
            if own:
                owners.setdefault(normalise(own), set()).add(entry.id)

    payload = json.loads(ALIASES.read_text(encoding="utf-8"))
    clashes: list[str] = []
    for entry_id, hand_written in payload.items():
        if entry_id.startswith("_"):
            continue
        for alias in hand_written:
            others = owners.get(normalise(alias), set()) - {entry_id}
            if others:
                clashes.append(f"{alias!r} on {entry_id} is already the name of {sorted(others)}")
    assert not clashes, "\n  ".join(clashes)


# ---------------------------------------------------------------------------
# Coverage: the data file is the ceiling on the whole news pipeline
# ---------------------------------------------------------------------------
#
# These tests are about the *data*, not the matcher, and they are here because
# the discard invariant has a cost that only shows up on this side of it. Every
# agent in the pipeline resolves with `allow_llm=False`, so a place this file
# does not know is an article thrown away. "Discarded, never guessed" working
# correctly and the surface being empty are the same observation, and S31 was
# the sprint that paid the bill.


def test_the_road_layer_exists() -> None:
    """
    Roads were absent from this file by construction until S31: the harvest
    asked OpenStreetMap for places, junctions, markets and terminals and never
    for a `highway`. The first live crime extraction geocoded neither of its two
    results and one of them was `Satmasjid Road`.

    A re-harvest that drops the layer again — a mirror answering a road tile with
    nothing, a selector typo — would be invisible in every other test here.
    """
    roads = [e for e in load(GAZETTEER, ALIASES).entries if e.kind == "road"]
    assert len(roads) > 200, f"only {len(roads)} roads; the road layer looks broken"


def test_every_road_radius_is_inside_the_harvests_clamp() -> None:
    """
    A road's radius is measured rather than defaulted, so it is the one kind
    whose radius a bug can make arbitrary. It reaches a published flag directly:
    `resolve_place` returns `entry.radius_m` and `live_risk` writes it as the
    flag's radius.
    """
    import importlib
    import sys as _sys

    _sys.path.insert(0, str(BACKEND / "scripts"))
    harvest = importlib.import_module("harvest_gazetteer")

    bad = [
        f"{e.id} r={e.radius_m}"
        for e in load(GAZETTEER, ALIASES).entries
        if e.kind == "road"
        and not (harvest.ROAD_MIN_RADIUS_M <= e.radius_m <= harvest.ROAD_MAX_RADIUS_M)
    ]
    assert not bad, bad[:5]


def test_an_arterial_too_long_to_pin_is_known_and_refused() -> None:
    """
    The discard invariant applied to extent rather than to a duplicate name.
    Mirpur Road is about 8 km; a pin at its midpoint would be up to 4 km from the
    incident. The entry is kept — so the query never falls through to the LLM
    tier, which would invent a point — and refused.

    `matches_ambiguous_only` is the assertion that matters: it is what stops
    `resolve_place` asking a model. "Known and declined" and "never heard of it"
    must not look the same here.
    """
    g = load(GAZETTEER, ALIASES)
    unpinnable = [e for e in g.entries if e.kind == "road" and e.ambiguous]
    assert unpinnable, (
        "no road was too long to pin, which means either the harvest found no "
        "arterials or ROAD_REFUSE_HALF_SPAN_M stopped doing anything"
    )
    for entry in unpinnable[:20]:
        for name in entry.all_names():
            hit = g.resolve(name)
            assert hit is None or hit.entry.id != entry.id, (
                f"{name!r} is too long to pin but resolved to itself"
            )


def test_a_road_short_enough_to_pin_resolves() -> None:
    """
    The other direction, and the measured failure S31 exists to fix: a crime
    report naming `Satmasjid Road` was discarded on 2026-10-14 because no entry
    of any kind carried that name.
    """
    g = load(GAZETTEER, ALIASES)
    pinnable = [e for e in g.entries if e.kind == "road" and not e.ambiguous]
    assert pinnable, "every road was refused, which is safe and useless"


def test_the_outer_city_is_inside_the_box() -> None:
    """
    The old box was 23.70-23.90 / 90.33-90.50 and stopped inside Dhaka. Every
    name below is in one of the two city corporations and sat outside it, so an
    article about any of them was discarded for being out of area rather than
    for anything to do with the article.
    """
    g = load(GAZETTEER, ALIASES)
    missing = [
        name
        for name in ("Uttarkhan", "Dakshinkhan", "Turag", "Demra", "Matuail", "Kadamtali")
        if g.resolve(name) is None and not g.matches_ambiguous_only(name)
    ]
    assert not missing, f"the box still does not cover {missing}"


def test_adding_the_vernacular_layer_did_not_remove_the_places_it_is_named_after() -> None:
    """
    The regression S31's own new layers would have caused, checked against the
    real file rather than a fixture.

    OSM names Dhaka's bus stops after the areas they serve — plain "Mohakhali",
    not "Mohakhali Bus Stop" — and the stop node sits well over the merge radius
    from the area's label node. Without `_drop_borrowed_names`, the harvest reads
    that as two places sharing a name, marks both ambiguous, and the loader
    refuses the area. Adding coverage would have *removed* these.
    """
    g = load(GAZETTEER, ALIASES)
    for name in ("Mohakhali", "Farmgate", "Shewrapara", "Agargaon", "Karwan Bazar", "Gabtoli"):
        assert g.resolve(name) is not None, (
            f"{name!r} stopped resolving — check `_drop_borrowed_names` in the harvest"
        )


def test_a_lookup_is_cheap_enough_for_the_request_path() -> None:
    """
    `resolve_place` is on `/geo/resolve`, and the gazetteer grew roughly sixfold
    in S31. Both scanning tiers used to call `normalise`, `tokens` and `numbers`
    on every name of every entry on every lookup, and the fuzzy tier ran
    `difflib` over all of them — measured at 13.6 ms per query with 1,022
    entries, which would have been about 80 ms with six thousand.

    The bound is loose on purpose: this asserts the index exists, not a
    particular machine's speed. A reintroduced full scan misses it by an order of
    magnitude, which is the only regression worth failing a build over.
    """
    import time

    g = load(GAZETTEER, ALIASES)
    queries = [
        "Mirpur 10 golchattar", "Satmasjid Road", "Dhanmondi", "Sector 11",
        "zzzzqqqq not a place", "Mohakhali", "কারওয়ান বাজার", "Road No 5",
        "Uttara Sector 7", "Farmgate", "মিরপুর ১০", "Gulshan Avenue",
    ]
    started = time.perf_counter()
    for _ in range(10):
        for query in queries:
            g.resolve(query)
    per_query = (time.perf_counter() - started) / (10 * len(queries))
    assert per_query < 0.025, f"{per_query * 1000:.1f} ms per lookup — the index is gone"
