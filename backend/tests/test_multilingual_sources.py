"""
The 2026-10-14 source expansion: three publishers became nine, two scripts, one
extraction budget shared between them.

Every case here is a defect that was live at some point during that change, not a
hypothetical. Three of them were found by running the pipeline against the real
sites rather than by reasoning about it, and they share a shape worth naming: the
pipeline kept working, and silently produced nothing. A source that fetches, parses
and stores zero documents raises no error anywhere.
"""

from __future__ import annotations

from app.agents.live_risk import (
    EXCLUDED_SECTIONS,
    INCIDENT_WORDS_EN,
    interleave,
    is_relevant,
    names_an_incident,
    place_candidates,
)
from app.agents.scheduled_risk import is_announcement
from app.contracts.risk import RawDocument
from app.ingestion.sources import SOURCES
from app.ingestion.sources.base import ArticleRef, article_body, latin_paragraphs
from app.policy.independence import independent_publishers, is_confirmable

from datetime import UTC, datetime, timedelta

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def ref(title: str, *, section: str = "bangladesh", hours_old: int = 1) -> ArticleRef:
    return ArticleRef(
        url=f"https://example.com/{section}/123/slug",
        title=title,
        published_at=NOW - timedelta(hours=hours_old),
    )


def doc(doc_id: str, source_id: str) -> RawDocument:
    return RawDocument(
        doc_id=doc_id,
        source_id=source_id,
        url=f"https://example.com/{doc_id}",
        fetched_at=NOW,
        published_at=NOW,
        language="bn",
        title="t",
        body="b",
    )


# ---------------------------------------------------------------------------
# The English body would have been filtered away as "not Bangla"
# ---------------------------------------------------------------------------


def test_an_english_body_survives_and_a_bangla_body_still_filters_on_script() -> None:
    """
    The defect that would have made Dhaka Tribune a source that stores nothing.

    `bangla_paragraphs` drops every paragraph with no Bangla character in it, which
    is right for a Bangla article — that is exactly how its photo captions and
    credits read — and deletes an English article in full.
    """
    english = [
        "A fire broke out at the pharmaceutical factory of Drug International Limited.",
        "Photo: X",
        "",
    ]
    assert article_body(english, language="en").startswith("A fire broke out")
    assert article_body(english, language="bn") == ""

    # The Bangla rule filters on *script*, so it drops the Latin-only credit line
    # and keeps a Bangla caption. That is the existing, intended behaviour: a Bangla
    # caption is Bangla prose about the event and costs nothing to carry into the
    # extraction, while "Photo: Channel 24" is navigation furniture.
    bangla = ["রাজধানীর মিরপুরে বাসে আগুন লেগেছে।", "Photo: Channel 24"]
    assert article_body(bangla, language="bn") == "রাজধানীর মিরপুরে বাসে আগুন লেগেছে।"


def test_short_latin_nodes_are_not_body_text() -> None:
    assert latin_paragraphs(["Topics:", "AFP", "", "x" * 39]) == ""
    assert latin_paragraphs(["y" * 40]) == "y" * 40


def test_mixed_language_documents_take_the_bangla_rule() -> None:
    """A mixed document is a Bangla one with English in it; the script filter wins."""
    assert article_body(["ঢাকায় আগুন।", "Reuters"], language="mixed") == "ঢাকায় আগুন।"


# ---------------------------------------------------------------------------
# The English headline filter
# ---------------------------------------------------------------------------


def test_english_headlines_are_matched_at_word_boundaries_not_as_substrings() -> None:
    """
    Why `INCIDENT_WORDS_EN` needs a regex where the Bangla list needs `in`.

    Bangla inflects by suffix, so a substring test is what catches আগুনে from আগুন.
    English substrings are a trap, and the two cases below are the expensive ones:
    `jam` is inside two Bangladeshi proper nouns that appear in the news constantly,
    and every false match costs a fetch and an extraction out of the free tier.
    """
    assert names_an_incident("Fire breaks out at drug factory in Tongi")
    assert names_an_incident("Road blocked in Mirpur")
    assert names_an_incident("Workers blockade airport road")

    assert not names_an_incident("Jamuna Bank opens new branch")
    assert not names_an_incident("Jamalpur farmers get subsidy")
    assert not names_an_incident("Minister fired from cabinet post")


def test_english_stems_catch_their_inflections() -> None:
    assert names_an_incident("Protesters block Shahbagh")
    assert names_an_incident("Truck overturned on Mirpur Road")
    assert names_an_incident("Blockade continues")


def test_both_vocabularies_are_tried_on_every_headline() -> None:
    """
    Dhaka English copy keeps Bangla loan words and vice versa, and a headline is
    too short to language-detect. Trying both costs one regex.
    """
    assert names_an_incident("Hartal called in Dhaka tomorrow")
    assert names_an_incident("মিরপুরে বাসে আগুন")


def test_the_incident_word_list_has_no_accidental_empties() -> None:
    assert all(word.strip() for word in INCIDENT_WORDS_EN)


# ---------------------------------------------------------------------------
# Desk names, which are per-publisher and were twice wrong
# ---------------------------------------------------------------------------


def test_singular_sport_desk_is_excluded() -> None:
    """
    Dhaka Tribune files sport at /sport/, and the list had only the plural. Found on
    the first live run: "US women rally to draw 2-2 with Spain" matched `rally`.
    """
    assert not is_relevant(ref("US women rally to draw 2-2 with Spain", section="sport"), NOW)


def test_foreign_desk_is_excluded() -> None:
    """Bangla Tribune's foreign desk; a Saudi drone strike matched আগুন."""
    assert not is_relevant(
        ref("সৌদি আরবে হুথিদের হামলা, আরামকোর ভবনে আগুন", section="foreign"), NOW
    )


def test_domestic_desks_near_dhaka_are_deliberately_not_excluded() -> None:
    """
    `country-news` and `whole-country` carry Tongi, Gazipur and Narayanganj, which
    are on the roads out of Dhaka. The pilot box decides distance, not this list.
    """
    assert "country-news" not in EXCLUDED_SECTIONS
    assert "whole-country" not in EXCLUDED_SECTIONS
    assert "capital" not in EXCLUDED_SECTIONS


# ---------------------------------------------------------------------------
# Romanised place names
# ---------------------------------------------------------------------------


def test_english_filler_is_stripped_and_numbers_are_kept() -> None:
    """
    The premise of adding an English publisher at all: 98.8% of gazetteer entries
    carry a `name_en`, so romanised text resolves — once the copy's wrapping words
    are removed the same way the Bangla ones are.
    """
    assert "Shahbagh intersection" in place_candidates("the capital's Shahbagh intersection area")
    # D03's number-identity rule has to survive romanisation: Mirpur 10 is not Mirpur 1.
    assert all("10" in candidate for candidate in place_candidates("Mirpur 10 circle"))


def test_a_generic_english_tail_is_stripped_only_from_the_end() -> None:
    assert "Mohakhali" in place_candidates("Mohakhali bus terminal")
    assert "Mirpur" in place_candidates("Mirpur Road")


def test_english_tail_matching_ignores_case() -> None:
    assert "Mirpur" in place_candidates("Mirpur road")
    assert "Mirpur" in place_candidates("Mirpur ROAD")


def test_a_comma_separated_qualifier_becomes_its_own_candidate() -> None:
    """
    Found on the first live crime extraction, 2026-10-14. Dhaka Tribune reported an
    assault at "Road No 1 in Lake Circus, Kalabagan"; `Kalabagan` is in the
    gazetteer and resolves on its own, and the full phrase did not — so a located
    report was discarded for want of a comma.
    """
    candidates = place_candidates("Road No 1 in Lake Circus, Kalabagan")
    assert "Kalabagan" in candidates
    # The whole phrase is still tried first, so a place the gazetteer knows in full
    # always beats its own less specific qualifier.
    assert candidates[0] == "Road No 1 in Lake Circus, Kalabagan"


def test_comma_segments_work_in_bangla_too() -> None:
    assert "ধানমন্ডি" in place_candidates("সাতমসজিদ রোড, ধানমন্ডি")


def test_a_comma_segment_is_still_a_subphrase_of_what_was_written() -> None:
    """The invariant has to survive the new reduction, not just the old two."""
    written = "Road No 1 in Lake Circus, Kalabagan"
    words = set(written.replace(",", " ").replace("-", " ").casefold().split())
    for candidate in place_candidates(written):
        assert set(candidate.replace(",", " ").casefold().split()) <= words


def test_a_place_with_no_comma_is_unaffected() -> None:
    assert place_candidates("Mirpur 10 circle")[0] == "Mirpur 10 circle"
    assert place_candidates("শাহবাগ মোড়")[0] == "শাহবাগ মোড়"


def test_a_bare_category_word_is_left_alone_to_fail() -> None:
    """`road` on its own identifies nowhere, and must be refused rather than trimmed."""
    assert place_candidates("road") == ["road"]


def test_every_candidate_is_a_subphrase_of_what_was_written() -> None:
    """
    The "discarded, never guessed" invariant, in its romanised form. Every candidate
    is built by removing words, so it can make a match possible and never make one up.
    """
    written = "near the capital's Gulshan 2 circle area"
    words = set(written.replace("-", " ").casefold().split())
    for candidate in place_candidates(written):
        assert set(candidate.casefold().split()) <= words


# ---------------------------------------------------------------------------
# The extraction budget, shared across nine publishers
# ---------------------------------------------------------------------------


def test_the_queue_takes_one_document_per_publisher_in_turn() -> None:
    batches = [
        [doc("a1", "prothom_alo"), doc("a2", "prothom_alo"), doc("a3", "prothom_alo")],
        [doc("b1", "samakal")],
        [doc("c1", "ittefaq"), doc("c2", "ittefaq")],
    ]
    assert [d.doc_id for d in interleave(batches)] == ["a1", "b1", "c1", "a2", "c2", "a3"]


def test_truncating_the_interleaved_queue_still_reaches_every_publisher() -> None:
    """
    The reason this function exists. Concatenating and then cutting to the free-tier
    budget means the first publisher fills it, so a second outlet's account of the
    same event is never extracted in the same run — and a flag reaches `confirmed`
    only when two independent publishers are seen to describe one event. The surface
    would have stayed entirely unconfirmed however many outlets were added.
    """
    batches = [[doc(f"{s}{i}", s) for i in range(8)] for s in ("s1", "s2", "s3", "s4", "s5")]

    concatenated = [d for batch in batches for d in batch][:12]
    assert len({d.source_id for d in concatenated}) == 2  # the old behaviour

    assert len({d.source_id for d in interleave(batches)[:12]}) == 5


def test_a_publisher_that_returned_nothing_just_drops_out() -> None:
    assert [d.doc_id for d in interleave([[doc("a", "x")], [], [doc("b", "y")]])] == ["a", "b"]
    assert interleave([]) == []


# ---------------------------------------------------------------------------
# Nine publishers, and two of them are one newsroom
# ---------------------------------------------------------------------------


def test_the_registry_has_no_duplicate_source_ids() -> None:
    ids = [source.source_id for source in SOURCES]
    assert len(ids) == len(set(ids))


def test_every_source_declares_a_language_the_schema_allows() -> None:
    """`raw_documents.language` is CHECK-constrained; a typo here fails at insert."""
    for source in SOURCES:
        assert getattr(source, "language", "bn") in {"bn", "en", "mixed"}


def test_the_two_tribunes_do_not_corroborate_each_other() -> None:
    """
    Both were added in the same change, and they are one house. Letting them confirm
    each other would manufacture agreement rather than find it.
    """
    assert independent_publishers({"dhaka_tribune", "bangla_tribune"}) == {"tribune_group"}
    assert not is_confirmable({"dhaka_tribune", "bangla_tribune"}, minimum=2)
    assert is_confirmable({"dhaka_tribune", "samakal"}, minimum=2)


def test_unrelated_publishers_still_corroborate() -> None:
    assert is_confirmable({"prothom_alo", "jugantor", "ittefaq"}, minimum=2)


# ---------------------------------------------------------------------------
# The announcement filter, which is also two-language now
# ---------------------------------------------------------------------------


def test_an_english_announcement_needs_both_halves() -> None:
    assert is_announcement(ref("Hartal called for tomorrow in Dhaka"), NOW)
    # A future marker with no event, and an event with no future marker.
    assert not is_announcement(ref("Dhaka weather to improve tomorrow"), NOW)
    assert not is_announcement(ref("Procession paralyses Shahbagh"), NOW)


def test_the_two_halves_may_be_satisfied_in_different_languages() -> None:
    """Dhaka English copy writes "hartal called for tomorrow" — a Bangla loan word."""
    assert is_announcement(ref("হরতাল called for tomorrow"), NOW)
