"""
Rumour Guard: four outlets reporting one fire become one confirmed flag, not four.

D05, source S15. These tests cover the decisions the guard makes, in the order the
guard makes them, and they are deliberately split into two groups:

* **Pure logic** — independence, weight, geometry, merge arithmetic. No model, no
  database, fast, and run on every push.
* **Model-dependent** — the similarity judgement itself, skipped when the embedding
  model is unavailable. Skipping is correct here: a missing 90 MB download is an
  environment fact, and the guard is written to degrade to "publish separately,
  unconfirmed" when it happens. A test that failed instead would be reporting the
  environment as a defect.

The invariant that matters most — *no single source produces a confirmed flag* — is
tested in `test_single_source_never_confirmed.py`, which D05 extended to run against
this module rather than only against the fixture and the migration.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.rumour_guard import (
    DEDUP_MAX_DISTANCE_M,
    cosine_similarity,
    embed,
    embeddings_available,
    within_distance,
)
from app.core.config import settings
from app.policy.independence import (
    UNCONFIRMED_WEIGHT,
    confidence,
    independent_publishers,
    is_confirmable,
    owner_of,
)
from app.scoring.decay import effective_severity

pytestmark = pytest.mark.invariant

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Independence: who counts as a separate source
# ---------------------------------------------------------------------------


def test_one_outlet_reporting_twice_is_one_source() -> None:
    """
    The whole point. `source_count` must never grow because an outlet followed up.

    This is the failure mode that makes a verification tier meaningless: if a
    publisher can corroborate itself, then `confirmed` means "somebody wrote about
    this twice", which is not what the concept document promises.
    """
    assert independent_publishers(["channel24", "channel24", "channel24"]) == {"channel24"}
    assert not is_confirmable(["channel24", "channel24"], minimum=2)


def test_two_distinct_outlets_are_two_sources() -> None:
    assert independent_publishers(["channel24", "ekattor_tv"]) == {"channel24", "ekattor_tv"}
    assert is_confirmable(["channel24", "ekattor_tv"], minimum=2)


def test_an_unknown_publisher_is_its_own_owner() -> None:
    """
    The permissive default, stated as a test so the direction is deliberate.

    `_SAME_OWNER` is empty — same-owner detection is D05's pre-declared cut to Track
    B. An absent publisher therefore counts as independent, which means filling the
    map in later can only ever *reduce* what we are willing to confirm. A default
    that went the other way would silently refuse to confirm anything.
    """
    assert owner_of("some_outlet_we_have_never_heard_of") == "some_outlet_we_have_never_heard_of"


def test_the_ownership_map_is_honoured_when_it_has_entries(monkeypatch) -> None:
    """
    The Track B seam works; only the data is missing.

    Worth a test even though the map is empty, because the claim made in
    `independence.py` — "populate it and nothing else changes" — is otherwise
    untested and would quietly rot.
    """
    monkeypatch.setattr(
        "app.policy.independence._SAME_OWNER",
        {"outlet_a": "house_x", "outlet_b": "house_x"},
    )
    assert independent_publishers(["outlet_a", "outlet_b"]) == {"house_x"}
    assert not is_confirmable(["outlet_a", "outlet_b"], minimum=2), (
        "two outlets owned by one house must not corroborate each other"
    )


# ---------------------------------------------------------------------------
# Weight: unconfirmed is published, and discounted
# ---------------------------------------------------------------------------


def test_unconfirmed_is_discounted_but_not_silenced() -> None:
    """Plan S15: *published at reduced weight. Never suppressed, never promoted.*"""
    assert 0.0 < confidence("unconfirmed") < 1.0
    assert confidence("unconfirmed") == UNCONFIRMED_WEIGHT


def test_confirmed_counts_in_full() -> None:
    assert confidence("confirmed") == 1.0


def test_a_status_that_is_not_served_contributes_nothing() -> None:
    for status in ("expired", "rejected", "nonsense"):
        assert confidence(status) == 0.0


def test_a_single_source_fire_still_outranks_a_corroborated_minor_delay() -> None:
    """
    The ordering the weight exists to produce, as a test rather than as a comment.

    If discounting unconfirmed flags pushed a serious single-source event below a
    trivial corroborated one, the tier would be actively harmful — it would hide the
    early signal that is the argument for reading news at all. 0.6 is chosen to keep
    this true; a test is how we find out when someone retunes it.
    """
    unconfirmed_fire = effective_severity(severity_now=70.0, confidence=confidence("unconfirmed"))
    confirmed_delay = effective_severity(severity_now=25.0, confidence=confidence("confirmed"))
    assert unconfirmed_fire > confirmed_delay


def test_effective_severity_does_not_change_severity_now() -> None:
    """
    `severity_now` is the decay story; `effective_severity` is the decision weight.

    Keeping them separate is what lets the flag sheet say "74 when observed, 31 now,
    42% remaining" and have the arithmetic check out. Folding confidence into
    `severity_now` would make that line wrong for every unconfirmed flag — which is
    most of them.
    """
    assert effective_severity(severity_now=50.0, confidence=1.0) == 50.0
    assert effective_severity(severity_now=50.0, confidence=0.6) == 30.0


# ---------------------------------------------------------------------------
# Geometry: two claims must overlap to be one claim
# ---------------------------------------------------------------------------


def test_two_reports_of_one_place_overlap() -> None:
    """Mirpur-10 Circle, reported 200 m apart by two outlets."""
    assert within_distance(
        lat_a=23.8069, lon_a=90.3687, radius_a=400,
        lat_b=23.8051, lon_b=90.3687, radius_b=400,
    )


def test_a_vague_location_may_match_a_precise_one() -> None:
    """
    The allowance is the LARGER radius, and this is why.

    One outlet locates a fire to "Mirpur" (1.2 km area), another to a specific
    crossing (300 m). Requiring the tighter radius would refuse exactly the
    vague-plus-precise pair that most needs merging — and vagueness is the normal
    case in news copy.
    """
    assert within_distance(
        lat_a=23.8069, lon_a=90.3687, radius_a=1200,
        lat_b=23.8130, lon_b=90.3687, radius_b=300,
    )


def test_two_neighbourhoods_do_not_overlap() -> None:
    """Bangshal and Mirpur-10 are ~8 km apart; no radius should bridge that."""
    assert not within_distance(
        lat_a=23.7104, lon_a=90.4074, radius_a=400,
        lat_b=23.8069, lon_b=90.3687, radius_b=400,
    )


def test_a_huge_radius_cannot_swallow_the_city() -> None:
    """
    `DEDUP_MAX_DISTANCE_M` caps the radius allowance.

    Without the cap, a chronic flag with a 12 km radius would match every news flag
    in Dhaka and merge them all into one event. The cap is the difference between
    "the radius decides" and "the radius is unbounded".
    """
    assert not within_distance(
        lat_a=23.7104, lon_a=90.4074, radius_a=20_000,
        lat_b=23.8800, lon_b=90.3900, radius_b=400,
    )
    assert DEDUP_MAX_DISTANCE_M < 20_000


# ---------------------------------------------------------------------------
# Similarity: cosine, and the configured threshold
# ---------------------------------------------------------------------------


def test_cosine_handles_degenerate_input() -> None:
    """Never raises, never returns NaN — a zero vector means "no signal", not a crash."""
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0  # mismatched lengths


def test_cosine_does_not_assume_normalised_input() -> None:
    """Called from tests with hand-written vectors as well as from `embed()`."""
    assert cosine_similarity([3.0, 0.0], [7.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_the_configured_threshold_is_the_measured_one_not_the_declared_one() -> None:
    """
    Guards a finding that cost a measurement to make.

    `DEMO_PLAN.md` §9 declared 0.82. Measured on this model and this text, 0.82
    merges 1 of 18 known duplicate pairs — the guard would be a no-op that looked
    implemented. If someone "restores" the planned value, this fails and points at
    `scripts/eval_dedup.py`.
    """
    assert settings.DEDUP_SIMILARITY_THRESHOLD < 0.80, (
        "0.82 was the planned threshold and it merges almost nothing on "
        "all-MiniLM-L6-v2. Re-run scripts/eval_dedup.py before changing this."
    )
    assert settings.DEDUP_SIMILARITY_THRESHOLD > 0.60, (
        "below ~0.7 the labelled set starts producing false merges, which put a "
        "confirmed badge on an event that did not happen"
    )


# The three phrasings of the Mohakhali bus fire, in the order outlets would publish
# them. Used by the next two tests because this is the event the first real live flag
# came from, so it is the one worth being honest about.
_MOHAKHALI = (
    "An AC bus caught fire at Mohakhali Bus Terminal, causing traffic delays.",
    "Fire broke out in a bus near Mohakhali terminal; traffic is being diverted.",
    "A passenger bus burned at the Mohakhali bus stand and the road is congested.",
)


@pytest.mark.skipif(not embeddings_available(), reason="embedding model unavailable")
def test_a_third_account_matches_the_accumulated_summaries() -> None:
    """
    The judgement in the shape production actually performs it.

    `find_duplicate()` compares the incoming summary against
    `string_agg(e.summary_en, ' | ')` — **every** summary already on the flag, not
    one of them. That has a useful property worth pinning down: corroboration gets
    *easier* as it accumulates, because the aggregate is a broader target than any
    single phrasing. Measured on this cluster: 0.718 against one summary, 0.736
    against two.

    So an early comparison can miss and a later one still land, which is the right
    direction for a verification tier to fail in.
    """
    accumulated = f"{_MOHAKHALI[0]} | {_MOHAKHALI[1]}"
    vectors = embed([_MOHAKHALI[2], accumulated])
    assert vectors is not None
    assert cosine_similarity(*vectors) >= settings.DEDUP_SIMILARITY_THRESHOLD


@pytest.mark.skipif(not embeddings_available(), reason="embedding model unavailable")
def test_accumulating_summaries_does_not_widen_the_net_to_a_different_fire() -> None:
    """
    The other half of the property above: a bigger target must not catch more.

    A *different* fire in the same area, scored against the same accumulated pair,
    has to stay out. It scores 0.595 — further below the threshold than it sits
    against either summary alone, so accumulation sharpens precision here rather
    than eroding it. That is not guaranteed in general, which is why it is a test.
    """
    accumulated = f"{_MOHAKHALI[0]} | {_MOHAKHALI[1]}"
    vectors = embed(
        ["A warehouse caught fire near Mohakhali rail gate, road partly blocked.", accumulated]
    )
    assert vectors is not None
    assert cosine_similarity(*vectors) < settings.DEDUP_SIMILARITY_THRESHOLD


@pytest.mark.skipif(not embeddings_available(), reason="embedding model unavailable")
def test_the_second_account_of_one_event_is_a_known_near_miss() -> None:
    """
    A measured limitation, written down instead of discovered on stage.

    The *second* phrasing of the Mohakhali fire scores **0.718** against the first —
    below the 0.72 threshold, and identical to the highest-scoring pair of genuinely
    different events in the labelled set. The classes are not separable on this
    signal, and that is a fact about one-line summaries, not a tuning error:
    "two reports of one fire in Bangshal" and "two fires in Bangshal hours apart"
    read almost the same.

    The consequences are accepted deliberately:

    * recall is ~56% at this threshold, so some real corroboration is missed and the
      flag stays `unconfirmed` with a duplicate pin. Cosmetic.
    * precision is 100% on the labelled set, so no distinct events are fused and no
      `confirmed` badge is invented. That is the side to err on.
    * **promotion is therefore demonstrated by the scripted replay**
      (`python -m app.agents promote-demo`), not by hoping two outlets phrase a fire
      similarly enough during a nine-minute demo.

    This test asserts the near-miss rather than ignoring it, so that a future change
    which fixes it — a cross-encoder, or embedding location alongside the summary —
    fails here and gets its improvement recorded instead of silently absorbed.
    """
    vectors = embed([_MOHAKHALI[0], _MOHAKHALI[1]])
    assert vectors is not None
    score = cosine_similarity(*vectors)
    assert score < settings.DEDUP_SIMILARITY_THRESHOLD, (
        f"this pair now scores {score:.3f}, at or above the threshold. The signal has "
        "improved -- re-run scripts/eval_dedup.py, record the new recall, and update "
        "this test and the Rough edges section of docs/walkthroughs/D05.md."
    )
    assert score > 0.60, "and it should still be recognisably close, not unrelated"


@pytest.mark.skipif(not embeddings_available(), reason="embedding model unavailable")
def test_a_fire_and_a_collision_are_not_one_event() -> None:
    vectors = embed(
        [
            "An AC bus caught fire at Mohakhali Bus Terminal, causing traffic delays.",
            "Two passengers died when a bus and an auto-rickshaw collided in Satkania.",
        ]
    )
    assert vectors is not None
    assert cosine_similarity(*vectors) < settings.DEDUP_SIMILARITY_THRESHOLD


@pytest.mark.skipif(not embeddings_available(), reason="embedding model unavailable")
def test_the_labelled_set_produces_no_false_merges_at_the_configured_threshold() -> None:
    """
    The eval set's precision claim, asserted rather than left in a script's output.

    Recall is deliberately NOT asserted: it is 56% by choice, and a test pinning it
    would turn an honest trade-off into a tripwire. Precision is the one that must
    not regress, because a false merge is a false `confirmed` claim.
    """
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "eval" / "dedup" / "clusters.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))

    offenders: list[str] = []
    for negative in data["hard_negatives"]:
        vectors = embed([negative["a"], negative["b"]])
        assert vectors is not None
        score = cosine_similarity(*vectors)
        if score >= settings.DEDUP_SIMILARITY_THRESHOLD:
            offenders.append(f"{score:.3f}  {negative['why']}")

    assert offenders == [], (
        "these distinct events would be merged into one flag at the configured "
        f"threshold of {settings.DEDUP_SIMILARITY_THRESHOLD}:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------


def test_the_dedup_window_is_hours_not_days() -> None:
    """
    Outlets follow each other within hours. A day apart is a different incident at
    the same corner — and the same corner is exactly where repeat incidents happen,
    so a generous window would merge them.
    """
    assert 1.0 <= settings.DEDUP_WINDOW_HOURS <= 12.0


def test_a_days_old_report_is_outside_the_window() -> None:
    """Expressed as arithmetic so the constant and the intent cannot drift apart."""
    window = timedelta(hours=settings.DEDUP_WINDOW_HOURS)
    assert NOW - timedelta(days=1) < NOW - window
