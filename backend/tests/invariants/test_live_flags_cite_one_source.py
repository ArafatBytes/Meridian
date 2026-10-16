"""
Invariants for the Live Risk Agent (D04). No database, no network, no model.

Three commitments, each of which the agent could quietly break:

1. **One article is one source, and the status follows the publisher.** Every
   flag the agent builds has `source_count == 1` whatever the model said. Its
   `status` is `confirmed` when the publisher is one we chose and checked
   (`policy.independence.VETTED_PUBLISHERS`) and `unconfirmed` otherwise — the
   2026-10-16 change. What the model says never touches it.
2. **Unresolvable locations are discarded, never guessed.** Places resolve through
   the gazetteer only; cleaning a place name may remove filler words but never
   substitute a different name; a fabricated place produces no flag.
3. **Mobility framing.** The pin's text is `framing.py`'s output, and the model's
   own summary never reaches it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents import live_risk
from app.agents.live_risk import (
    LIVE_KEY_PREFIX,
    discard_reason,
    flag_row,
    is_relevant,
    place_candidates,
    resolve_news_place,
    write_replay,
)
from app.contracts.risk import GeoResolution, IncidentKind, MobilityImpact, RawDocument
from app.ingestion.sources.base import ArticleRef
from app.llm.models import NewsIncident
from app.policy.framing import assert_mobility_safe, to_mobility_statement
from app.scoring.fixture import REPLAY_PATH, check_rows, fixture_rows

pytestmark = pytest.mark.invariant

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)

DOC = RawDocument(
    doc_id="a" * 64,
    source_id="ekattor_tv",
    url="https://ekattor.tv/capital/1/x",
    fetched_at=NOW,
    published_at=NOW - timedelta(minutes=40),
    language="bn",
    title="মিরপুরে বাসে আগুন, সড়ক বন্ধ",
    body="রাজধানীর মিরপুর ১০ নম্বর গোলচত্বরে একটি বাসে আগুন লাগে।",
)

PLACE = GeoResolution(
    lat=23.8069,
    lon=90.3687,
    radius_m=150,
    resolved_name="Mirpur-10 Circle",
    method="gazetteer",
    confidence=1.0,
)

UNRESOLVED = GeoResolution(
    lat=0.0, lon=0.0, radius_m=1, resolved_name="x", method="unresolved", confidence=0.0
)


def incident(**overrides: object) -> NewsIncident:
    fields: dict[str, object] = {
        "kind": "fire",
        "location_text": "মিরপুর ১০ গোলচত্বর",
        "mobility_impact": MobilityImpact.ROAD_BLOCKED,
        "severity_hint": "high",
        "summary_en": "A bus caught fire; the road is blocked.",
        "confidence": 0.9,
    }
    fields.update(overrides)
    return NewsIncident.model_validate(fields)


# ---------------------------------------------------------------------------
# 1. One article is one source, and one source is never confirmed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [k.value for k in IncidentKind if k is not IncidentKind.CHRONIC])
@pytest.mark.parametrize("impact", [i for i in MobilityImpact if i is not MobilityImpact.NONE])
def test_every_live_flag_cites_exactly_one_source(kind: str, impact: MobilityImpact) -> None:
    """
    One article is one source, for every kind and every impact.

    `source_count` is the part the model must never be able to move: it is what
    the flag sheet reports and what `independent_publishers` counts.
    """
    row = flag_row(
        doc=DOC,
        index=0,
        incident=incident(kind=kind, mobility_impact=impact, confidence=1.0),
        place=PLACE,
    )
    assert row["source_count"] == 1
    assert len(row["sources"]) == 1
    assert row["event_key"].startswith(LIVE_KEY_PREFIX)


def test_a_vetted_publisher_produces_a_confirmed_flag() -> None:
    """
    The 2026-10-16 change at the point of writing. `DOC` is Ekattor TV, which is
    in `SOURCES` and therefore in `VETTED_PUBLISHERS`.
    """
    row = flag_row(
        doc=DOC,
        index=0,
        incident=incident(kind="fire", mobility_impact=MobilityImpact.ROAD_BLOCKED),
        place=PLACE,
    )
    assert row["status"] == "confirmed"


def test_an_unvetted_publisher_does_not() -> None:
    """
    The condition, not the constant.

    Nothing un-vetted is ingested today, so this is the test that stops the
    condition being optimised away into `"confirmed"` — which is exactly the
    cheap change that would make the map look better and mean nothing. A source
    nobody surveyed gets the old treatment: unconfirmed until corroborated.
    """
    # Pydantic, not a dataclass.
    row = flag_row(
        doc=DOC.model_copy(update={"source_id": "some_blog"}),
        index=0,
        incident=incident(kind="fire", mobility_impact=MobilityImpact.ROAD_BLOCKED),
        place=PLACE,
    )
    assert row["status"] == "unconfirmed"


def test_a_live_flag_passes_the_fixture_constraints() -> None:
    """The same checks that mirror the table's CHECK constraints, run on an agent row."""
    row = flag_row(doc=DOC, index=0, incident=incident(), place=PLACE)
    check_rows([{**row, "event_key": "seed-" + row["event_key"]}])


def test_the_flag_cites_the_article_it_came_from() -> None:
    source = flag_row(doc=DOC, index=0, incident=incident(), place=PLACE)["sources"][0]
    assert source["source_id"] == DOC.source_id
    assert source["url"] == DOC.url
    assert source["title"] == DOC.title


def test_no_flag_is_written_without_a_derived_expiry() -> None:
    """`expires_at` is the trigger's to derive; a row that carried one would be ignored."""
    assert "expires_at" not in flag_row(doc=DOC, index=0, incident=incident(), place=PLACE)


# ---------------------------------------------------------------------------
# 2. Discarded, never guessed
# ---------------------------------------------------------------------------


def test_an_unresolved_place_is_discarded() -> None:
    assert discard_reason(incident(), UNRESOLVED) == "unresolved_location"


def test_a_low_confidence_extraction_is_discarded() -> None:
    assert discard_reason(incident(confidence=0.3), PLACE) == "low_confidence"


def test_an_event_that_does_not_affect_movement_is_discarded() -> None:
    assert discard_reason(incident(mobility_impact=MobilityImpact.NONE), PLACE) == "rejected"


def test_a_located_confident_mobility_event_is_published() -> None:
    assert discard_reason(incident(), PLACE) is None


@pytest.mark.parametrize(
    "written",
    [
        "রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়",
        "কড়াইল বস্তি",
        "মিরপুর-১০",
        "যাত্রাবাড়ী মোড়",
        "মহাখালী বাস টার্মিনালে",
    ],
)
def test_cleaning_a_place_only_removes_words_never_adds_them(written: str) -> None:
    original_words = set(written.replace("-", " ").split())
    for candidate in place_candidates(written):
        assert set(candidate.replace("-", " ").split()) <= original_words, candidate


async def test_news_phrasing_resolves_to_the_place_it_names() -> None:
    resolution = await resolve_news_place("রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়")
    assert resolution.method == "gazetteer"
    assert "Mirpur" in resolution.resolved_name and "10" in resolution.resolved_name


async def test_a_generic_place_type_tail_does_not_hide_the_place() -> None:
    """
    Regression, 2026-10-08. A real bus fire at Mohakhali Bus Terminal was extracted
    at 0.95 confidence and then discarded as `unresolved_location`: the model was
    asked for the most specific place name, answered মহাখালী বাস টার্মিনালে, and
    that phrase resolved to nothing while মহাখালী alone resolves at 1.00. The most
    specific answer was the least resolvable one, so live ingestion had never once
    published a flag.
    """
    resolution = await resolve_news_place("মহাখালী বাস টার্মিনালে")
    assert resolution.method == "gazetteer"
    assert "Mohakhali" in resolution.resolved_name


@pytest.mark.parametrize(
    "written,expected_name",
    [
        # A place the gazetteer knows in full must resolve to itself, never to its
        # own prefix -- otherwise this fix would trade precision for recall.
        ("মিরপুর ১০ গোলচত্বর", "Mirpur-10 Circle"),
        ("যাত্রাবাড়ী চৌরাস্তা", "Jatrabari Mor"),
        ("কারওয়ান বাজারে", "Karwan Bazar"),
    ],
)
async def test_a_known_place_resolves_to_itself_not_its_prefix(
    written: str, expected_name: str
) -> None:
    resolution = await resolve_news_place(written)
    assert resolution.resolved_name == expected_name


async def test_a_bare_place_type_identifies_nowhere() -> None:
    """`বাজারে` is a category, not a place. Trimming must not leave it resolvable."""
    assert (await resolve_news_place("বাজারে")).method == "unresolved"


async def test_a_place_that_does_not_exist_stays_unresolved() -> None:
    resolution = await resolve_news_place("রাজধানীর গুলশান ৯৭ নম্বর গোলচত্বর এলাকায়")
    assert resolution.method == "unresolved"


async def test_ingestion_never_asks_the_llm_where_a_place_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bulk resolution is gazetteer-only: free, deterministic, zero fabrications in D03."""

    async def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("the Live Risk Agent must not spend an LLM request on a place")

    monkeypatch.setattr("app.geo.agent.complete", forbidden)
    resolution = await resolve_news_place("একটি অজানা জায়গা")
    assert resolution.method == "unresolved"


# ---------------------------------------------------------------------------
# 3. The pin's words are framing.py's
# ---------------------------------------------------------------------------


def test_the_statement_is_framing_output_not_the_models_summary() -> None:
    hostile = incident(summary_en="Violent clash, mob attacked buses, very dangerous area")
    row = flag_row(doc=DOC, index=0, incident=hostile, place=PLACE)
    assert row["mobility_statement"] == to_mobility_statement(
        kind=IncidentKind.FIRE, impact=MobilityImpact.ROAD_BLOCKED, place=PLACE.resolved_name
    )
    assert_mobility_safe(row["mobility_statement"])
    assert "mob" not in row["mobility_statement"].lower()


# ---------------------------------------------------------------------------
# Relevance filtering spends the quota, so it is pinned too
# ---------------------------------------------------------------------------


def test_relevance_needs_incident_vocabulary_a_dhaka_desk_and_recency() -> None:
    def ref(title: str, section: str = "capital", hours_old: float = 1.0) -> ArticleRef:
        return ArticleRef(
            url=f"https://ekattor.tv/{section}/1/x",
            title=title,
            published_at=NOW - timedelta(hours=hours_old),
        )

    assert is_relevant(ref("মিরপুরে বাসে আগুন"), NOW)
    assert not is_relevant(ref("বিমানের বহরে যুক্ত হচ্ছে এয়ারবাস"), NOW)
    assert not is_relevant(ref("ইউক্রেনে আগুন", section="international"), NOW)
    assert not is_relevant(ref("মিরপুরে বাসে আগুন", hours_old=30), NOW)


# ---------------------------------------------------------------------------
# The offline replay holds no prose and loads like any fixture
# ---------------------------------------------------------------------------


def test_a_replay_entry_round_trips_through_the_fixture_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = {
        "event_key": "seed-live-abc-0",
        "kind": "fire",
        "lat": PLACE.lat,
        "lon": PLACE.lon,
        "radius_m": 400,
        "severity_0": 91.0,
        "half_life_hours": 3.5,
        "mobility_impact": "road_blocked",
        "place": PLACE.resolved_name,
        "observed_offset_hours": -0.5,
        "source_count": 1,
        "sources": [
            {
                "source_id": "ekattor_tv",
                "url": DOC.url,
                "title": DOC.title,
                "published_offset_hours": -0.4,
            }
        ],
    }
    replay = tmp_path / "live_replay.json"
    write_replay([entry], NOW, replay)
    written = json.loads(replay.read_text(encoding="utf-8"))
    assert all("mobility_statement" not in flag for flag in written["flags"])

    monkeypatch.setattr("app.scoring.fixture.REPLAY_PATH", replay)
    rows = fixture_rows(NOW, include_chronic=False, include_replay=True)
    replayed = [r for r in rows if r["event_key"] == "seed-live-abc-0"]
    assert len(replayed) == 1
    assert replayed[0]["sources"][0]["title"] == DOC.title
    assert_mobility_safe(replayed[0]["mobility_statement"])


def test_the_committed_replay_declares_no_mobility_statement() -> None:
    if not REPLAY_PATH.is_file():
        pytest.skip("no replay captured yet")
    data = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    assert all("mobility_statement" not in f for f in data["flags"])
    assert all(f["event_key"].startswith("seed-live-") for f in data["flags"])


def test_the_seeder_never_loads_the_replay() -> None:
    """The live originals are already in the database; seeding the capture would double them."""
    keys = {r["event_key"] for r in fixture_rows(NOW)}
    assert not any(k.startswith("seed-live-") for k in keys)
    assert live_risk.REPLAY_PATH == REPLAY_PATH
