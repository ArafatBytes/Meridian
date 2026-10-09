"""
Invariant: **a photo proposes, it never accuses.**

D07, ADR 0006. The design rests on one rule — the model reports visible cues,
our code turns them into *at most* a suggestion, and a human confirms it. Every
test here guards a way that rule could be broken while the code still looked
fine and the screen still rendered.

Four things that would each be silently wrong:

1. **`unclear` proposing something.** The most likely regression: someone treats
   anything that is not `no` as a hit, and ambiguity starts generating
   accusations. This is the one worth a test on its own.
2. **A category appearing that no photograph can establish.** Only `fraud` is
   now on that list -- it is a document or a conversation, not a scene -- and a
   rule table that grows will eventually be tempted by it. Theft and robbery
   came off the list on 2026-10-10: goods going into a bag, and two people
   pulling one bag, are both observable. The category stays `weak` and the
   reporter still confirms.
3. **A benign frame producing a category.** All cues `no` must mean nothing
   proposed, not "other" and not a low-confidence guess.
4. **The replay fixture storing our own conclusions.** If `proposed_category`
   were captured rather than re-derived, changing the rules would silently stop
   taking effect for exactly the photos the demo uses.
"""

from __future__ import annotations

import pytest

from app.llm.models import CrimeCues
from app.vision.mapping import (
    CUE_FIELDS,
    NOTHING,
    PROPOSABLE_FROM_PHOTO,
    UNREACHABLE_FROM_PHOTO,
    cross_check,
    propose,
)

pytestmark = pytest.mark.invariant


def cues(**overrides: object) -> CrimeCues:
    """A benign set of cues, with the named ones changed."""
    base: dict[str, object] = {field: "no" for field in CUE_FIELDS}
    base.update(
        people_count=2,
        scene="street",
        description="Two people stand on a footpath.",
    )
    base.update(overrides)
    return CrimeCues(**base)  # type: ignore[arg-type]


# --- 1. unclear is not a yes --------------------------------------------------


@pytest.mark.parametrize("field", CUE_FIELDS)
def test_a_single_unclear_cue_proposes_nothing(field: str) -> None:
    assert propose(cues(**{field: "unclear"})) == NOTHING


def test_every_cue_unclear_proposes_nothing() -> None:
    """
    The ambiguous photo. A model that cannot tell what it is looking at must not
    produce a category, however many cues it is unsure about.
    """
    assert propose(cues(**{f: "unclear" for f in CUE_FIELDS})) == NOTHING


def test_unclear_does_not_combine_into_a_proposal() -> None:
    """`unclear` plus `unclear` is not evidence, however it is counted."""
    result = propose(cues(physical_confrontation="unclear", weapon_visible="unclear"))
    assert result.category is None
    assert result.confidence == "none"


# --- 2. and 3. what may be proposed, and when ---------------------------------


def test_a_benign_frame_proposes_nothing() -> None:
    result = propose(cues())
    assert result.category is None
    assert result.confidence == "none"
    assert result.cues_fired == ()


@pytest.mark.parametrize(
    "fired",
    [
        {"physical_confrontation": "yes"},
        {"weapon_visible": "yes"},
        {"property_damage": "yes"},
        {"forced_entry": "yes"},
        {"unwanted_pursuit": "yes"},
        {"struggle_over_property": "yes"},
        {"goods_concealed": "yes"},
        {"weapon_visible": "yes", "physical_confrontation": "yes"},
        {"forced_entry": "yes", "property_damage": "yes"},
        {"struggle_over_property": "yes", "weapon_visible": "yes"},
        {"struggle_over_property": "yes", "physical_confrontation": "yes"},
        {f: "yes" for f in CUE_FIELDS},
    ],
)
def test_nothing_unreachable_is_ever_proposed(fired: dict[str, str]) -> None:
    """
    No combination of cues may produce `fraud`.

    Not a style preference: fraud is a document or a conversation, so proposing
    it would be the pipeline asserting something no photograph contains.
    """
    category = propose(cues(**fired)).category
    assert category not in UNREACHABLE_FROM_PHOTO
    if category is not None:
        assert category in PROPOSABLE_FROM_PHOTO


def test_a_proposal_always_says_which_cues_fired() -> None:
    """A suggestion with no stated grounds is not reviewable."""
    result = propose(cues(physical_confrontation="yes"))
    assert result.category is not None
    assert result.cues_fired
    assert result.reason


@pytest.mark.parametrize(
    "fired,expected",
    [
        ({"goods_concealed": "yes"}, "theft"),
        ({"struggle_over_property": "yes"}, "robbery"),
        ({"forced_entry": "yes"}, "burglary"),
        ({"physical_confrontation": "yes"}, "assault"),
        ({"unwanted_pursuit": "yes"}, "harassment"),
        ({"property_damage": "yes"}, "vandalism"),
    ],
)
def test_each_new_cue_reaches_its_category(fired: dict[str, str], expected: str) -> None:
    """
    Every cue must be able to produce something, or it is a question nobody acts
    on. Three of the four scenes in the 2026-10-09 test set failed exactly here:
    the models described them correctly and no cue covered what they described.
    """
    assert propose(cues(**fired)).category == expected


def test_strong_confidence_needs_two_independent_cues() -> None:
    assert propose(cues(physical_confrontation="yes")).confidence == "weak"
    assert propose(
        cues(physical_confrontation="yes", weapon_visible="yes")
    ).confidence == "strong"


# --- the text cross-check never changes the proposal --------------------------


@pytest.mark.parametrize(
    "text",
    ["they beat him", "my phone was stolen", "", None, "   "],
)
def test_cross_check_does_not_alter_the_proposal(text: str | None) -> None:
    """
    Text and photo are two independent accounts. Letting one edit the other would
    hide the single case worth seeing, where they disagree.
    """
    base = propose(cues(physical_confrontation="yes"))
    cross_check(base, text)
    assert propose(cues(physical_confrontation="yes")) == base


def test_silence_is_not_disagreement() -> None:
    """Most reports will not mention the cue. That must not read as a conflict."""
    result = propose(cues(physical_confrontation="yes"))
    assert cross_check(result, "Something happened here last night.") == "silent"


def test_no_proposal_means_no_agreement_to_assess() -> None:
    assert cross_check(NOTHING, "they beat him") == "silent"


# --- 4. the fixture stores the model, not us ----------------------------------


def test_replay_fixture_stores_no_conclusion_of_ours() -> None:
    """
    `CrimeCues` is what gets captured, so this is really a check on that model:
    it must carry only what a model can observe. The moment it gains a
    `proposed_category`, captures start freezing our rules alongside the
    model's answers, and editing the rules stops affecting the demo photos.
    """
    ours = {"proposed_category", "confidence", "reason", "cues_fired", "agreement"}
    assert ours.isdisjoint(CrimeCues.model_fields)
