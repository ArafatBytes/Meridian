"""
Cues to a candidate category. **This file is the design.**

The model answers five yes/no/unclear questions about what is visible. Nothing in
this module calls a model; it turns those answers into something a reporter can
confirm. Keeping it here rather than in the prompt buys three things:

* it is auditable — the rule that fired is a line you can read, not a sentence
  that persuaded a model;
* it is tunable without re-prompting, so changing policy costs no tokens and no
  re-measurement of the model;
* a hallucinated cue produces a wrong *cue*, which these rules can refuse,
  instead of a wrong accusation already rendered on screen.

The hard rule: **only `yes` proposes anything.** `unclear` never does. A photo
cannot show intent, consent, who started it, or whether it is staged, so the
honest output for an ambiguous frame is a description and no proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.llm.models import CrimeCues

Confidence = Literal["strong", "weak", "none"]
"""
Three bands, not a number.

The inherited pipeline printed figures like `0.73` that were the product of
weights nobody had validated. A band says what we actually know, and a judge
asking "what does 73% mean?" has a fair question with no answer. `strong` means
two or more independent cues agree; `weak` means one did.
"""

# Only `fraud` is beyond a photograph: it is a document or a conversation, not a
# scene. The rest can be *proposed*, never asserted.
#
# Theft and robbery were on this list until 2026-10-09, on the reasoning that a
# photo cannot show ownership or who took what. True — but it was the wrong
# conclusion. A photo *can* show goods going into a bag, or two people pulling
# one bag between them. Those are observable; the category is the uncertain part,
# and the uncertain part is exactly what `weak` confidence and the reporter's
# confirmation exist for. Refusing to propose anything was not more honest, it
# was just less useful.
UNREACHABLE_FROM_PHOTO: Final = ("fraud",)

PROPOSABLE_FROM_PHOTO: Final = (
    "assault", "burglary", "harassment", "robbery", "theft", "vandalism", "other",
)
"""Seven of the eight. Only `fraud` has no visual form at all."""

# First match wins, so the most specific combinations come first. Every entry
# requires `yes` on the cues it names.
_RULES: Final[tuple[tuple[tuple[str, ...], str, str], ...]] = (
    # Force plus a struggle over property is the shape of a robbery. The theft
    # itself is still not visible, which is why the reporter confirms.
    (
        ("struggle_over_property", "weapon_visible"),
        "robbery",
        "a weapon is visible and people are struggling over property",
    ),
    (
        ("struggle_over_property", "physical_confrontation"),
        "robbery",
        "people are in forceful contact and struggling over property",
    ),
    (
        ("weapon_visible", "physical_confrontation"),
        "assault",
        "a weapon is visible and people are in forceful contact",
    ),
    (
        ("forced_entry", "property_damage"),
        "burglary",
        "something has been forced open and property is damaged",
    ),
    # A bag being pulled between two people, with nothing else visible.
    (("struggle_over_property",), "robbery", "people are struggling over the same property"),
    (("goods_concealed",), "theft", "goods are being put into a bag, pocket or clothing"),
    (("physical_confrontation",), "assault", "people are in forceful physical contact"),
    (("forced_entry",), "burglary", "a lock, door, window or vehicle is being forced"),
    (("unwanted_pursuit",), "harassment", "one person is following or cornering another"),
    (("property_damage",), "vandalism", "property is broken, burnt or defaced"),
    # A weapon on its own. Not assault -- nothing is happening to anyone yet --
    # but not nothing either, so it is reported without claiming a category.
    (("weapon_visible",), "other", "a weapon is visible"),
)


@dataclass(frozen=True, slots=True)
class Proposal:
    """What our code is willing to suggest, and why. Never what gets filed."""

    category: str | None
    confidence: Confidence
    reason: str
    cues_fired: tuple[str, ...]

    @property
    def proposes_anything(self) -> bool:
        return self.category is not None


NOTHING: Final = Proposal(
    category=None,
    confidence="none",
    reason="nothing in the photo indicates a specific category",
    cues_fired=(),
)

CUE_FIELDS: Final = (
    "physical_confrontation",
    "weapon_visible",
    "property_damage",
    "forced_entry",
    "unwanted_pursuit",
    "struggle_over_property",
    "goods_concealed",
)


def propose(cues: CrimeCues) -> Proposal:
    """
    The candidate category for one set of cues, or `NOTHING`.

    `NOTHING` is a successful result, not a failure. It is what an empty street,
    a benign photo, or a frame the model could not read all produce, and the
    screen shows the description with no category attached.
    """
    fired = tuple(f for f in CUE_FIELDS if getattr(cues, f) == "yes")
    if not fired:
        return NOTHING

    for needed, category, reason in _RULES:
        if all(cue in fired for cue in needed):
            return Proposal(
                category=category,
                # Two cues that independently point the same way is the only thing
                # here worth calling strong.
                confidence="strong" if len(needed) > 1 else "weak",
                reason=reason,
                cues_fired=fired,
            )
    return NOTHING


Agreement = Literal["agrees", "disagrees", "silent"]

# What a reporter writes when they mean each category, in both scripts they write
# in. Deliberately short: this is a corroboration hint shown to a human, not a
# classifier, and a long list would start matching things it should not.
_CATEGORY_WORDS: Final[dict[str, tuple[str, ...]]] = {
    "assault": ("assault", "attack", "beat", "hit", "punch", "fight", "stab",
                "মারধর", "হামলা", "মারামারি", "আক্রমণ"),
    "burglary": ("burglary", "break-in", "broke in", "broke into", "forced",
                 "চুরি", "সিঁধ", "ভাঙ"),
    "harassment": ("harass", "follow", "followed", "stalk", "catcall", "tease",
                   "হয়রানি", "উত্যক্ত", "পিছু"),
    "vandalism": ("vandal", "smash", "smashed", "broke", "burnt", "burned",
                  "graffiti", "ভাঙচুর", "আগুন"),
    "other": ("weapon", "gun", "knife", "অস্ত্র", "ছুরি"),
    # `fraud` is never proposed from a photo, but a reporter can still write it,
    # and the mismatch is worth showing.
    "theft": ("theft", "stole", "stolen", "snatch", "pickpocket", "চুরি", "ছিনতাই"),
    "fraud": ("fraud", "scam", "cheated", "প্রতারণা", "জালিয়াতি"),
    "robbery": ("robbery", "snatch", "snatched", "mugged", "ছিনতাই", "ডাকাতি"),
}


def cross_check(proposal: Proposal, report_text: str | None) -> Agreement:
    """
    Does what the reporter wrote line up with what the photo showed?

    Three answers, and `silent` is the common one — most reports are short and
    will not mention the thing the photo shows. Silence is **not** disagreement,
    which is why it is its own value rather than a false.

    This is shown to the reporter as corroboration before they confirm. It never
    changes the proposal: text and photo are two independent accounts, and
    collapsing them here would hide the one case worth seeing, where they differ.
    """
    if proposal.category is None or not report_text or not report_text.strip():
        return "silent"

    text = report_text.casefold()
    if any(word in text for word in _CATEGORY_WORDS.get(proposal.category, ())):
        return "agrees"

    # The text clearly describes a different category. Worth surfacing: it usually
    # means the photo is of something else, such as the aftermath rather than the act.
    for category, words in _CATEGORY_WORDS.items():
        if category != proposal.category and any(word in text for word in words):
            return "disagrees"
    return "silent"
