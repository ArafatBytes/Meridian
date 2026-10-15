"""
Who counts as a *separate* source, and what an unconfirmed flag is worth.

Two policy questions, both small, both load-bear:

1. **Independence.** `status = 'confirmed'` requires two or more independent
   publishers. "Independent" is a judgement, not a fact about a string, and this
   module is where that judgement lives so that Rumour Guard stays mechanical.
2. **Weight.** An unconfirmed flag is *published at reduced weight* (plan S15) —
   never suppressed, never silently promoted.

Why a separate module rather than constants inside `agents/rumour_guard.py`: the
guard decides *whether two articles describe one event*, which is a similarity
problem. This decides *whether two publishers agreeing means anything*, which is
an editorial one. They change for different reasons, and the second is the one a
judge will push on.

---

### What is deliberately NOT here

**Same-owner and syndication detection.** `DEMO_PLAN.md` §D05 pre-declares it as
the first thing cut from this sprint, to Track B: *"Distinct publishers are enough
for the demo; this is the rigorous version, and it is the honest answer to give in
Q&A if asked."*

That cut is real and it has a real consequence, so it is written down rather than
implied: **two outlets owned by the same house, or both running the same wire
copy, count as two sources unless `_SAME_OWNER` says otherwise.**

Partly closed on 2026-10-14, when `SOURCES` went from three publishers to nine.
One pairing in that set is known and is now recorded — Dhaka Tribune and Bangla
Tribune are one house — because adding both while letting them corroborate each
other would have manufactured agreement rather than found it. The rest of the map
is still empty, and still for the original reason: guessing Bangladeshi media
ownership from memory would be worse than admitting the gap. See the comments on
`_SAME_OWNER` itself for what is asserted and what is not.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

__all__ = [
    "AUTHORITATIVE_PUBLISHERS",
    "UNCONFIRMED_WEIGHT",
    "confidence",
    "independent_publishers",
    "is_confirmable",
    "owner_of",
]


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------

_SAME_OWNER: Final[dict[str, str]] = {
    # publisher source_id -> owning group id.
    #
    # A publisher absent from this map is its own owner, which is the permissive
    # reading — so an entry here can only ever *reduce* the number of flags we are
    # willing to confirm, never increase it. That asymmetry is what makes it safe
    # to record a pairing we are confident about without waiting for a complete
    # ownership survey: the cost of a wrong entry is a confirmation we decline, and
    # the cost of a missing one is a confirmation we should not have made.
    #
    # Two entries sharing a value stop corroborating each other. Nothing else needs
    # to change.
    #
    # ---- what is recorded, and on what basis -------------------------------
    #
    # Dhaka Tribune and Bangla Tribune are sister papers — the same house, the
    # English and Bangla mastheads of one newsroom group, which is also why they
    # share a brand. Recorded on 2026-10-14, when both were added to `SOURCES` in
    # the same change: adding two outlets of one house and letting them confirm
    # each other would have been a *worse* surface than not adding them at all,
    # because it manufactures agreement.
    "dhaka_tribune": "tribune_group",
    "bangla_tribune": "tribune_group",
    #
    # ---- what is deliberately NOT recorded ---------------------------------
    #
    # The rest of the map stays empty. The other eight publishers in `SOURCES` are
    # each owned by a business house, several of which also own outlets we do not
    # read, and the pairings among the ones we DO read are not ones this codebase
    # can assert from memory. The module docstring's rule still holds: guessing
    # Bangladeshi media ownership would be worse than admitting the gap, because a
    # wrong pairing silently suppresses real corroboration and nothing would ever
    # point at this dictionary as the cause.
    #
    # The honest status is therefore: one pairing known and applied, the rest
    # outstanding. Syndication — two unrelated outlets running identical agency
    # copy — is a different problem and is handled elsewhere, by
    # `raw_documents.content_hash`.
}


# ---------------------------------------------------------------------------
# Authority — B11a, 2026-10-15
# ---------------------------------------------------------------------------

AUTHORITATIVE_PUBLISHERS: Final[frozenset[str]] = frozenset({"dmp_news"})
"""
Publishers that are the **primary record** of what they report, not a claim about it.

DMP News is the Dhaka Metropolitan Police's own outlet. When it says two muggers
were arrested in Uttara, that is the police's own account of their own action --
and a newspaper repeating it adds no independent verification, because the paper
got it from the release. Corroboration between a press release and its reprints is
agreement manufactured by syndication, which is the same hazard `_SAME_OWNER`
guards against wearing different clothes.

**What this grants, and what it deliberately does not.**

It grants *weight*: `confidence()` returns 1.0 instead of `UNCONFIRMED_WEIGHT`, so
an official report is not discounted as though it were an unverified rumour.

It does **not** grant `status = 'confirmed'`. That was the owner's first choice on
15 Oct and it cannot be done honestly: `confirmed` is enforced in the database by

    risk_flags_confirmed_needs_two_sources
    CHECK ((status <> 'confirmed') OR (source_count >= 2))

so a single-source confirmed flag is rejected on insert. The two ways round it are
both worse than the thing they buy -- a migration weakening the CHECK, while
`tests/invariants/test_single_source_never_confirmed.py` asserts it by reading the
*original* migration's text and would keep passing over the hole; or writing
`source_count = 2` for one source, which `risk_flags_sources_match_count` would
permit and which is simply false data. The owner chose weight on 15 Oct once the
constraint was shown.

So `confirmed` keeps meaning exactly one thing, at every layer: **two independent
publishers agreed.**

**This set is dangerous in the direction `_SAME_OWNER` is not.** An entry in the
ownership map can only ever *reduce* the flags we are willing to trust; an entry
here *increases* the weight of a single source. There is no permissive default to
fall back on. So it holds one member, it is asserted to hold one member by
`tests/invariants/test_single_source_never_confirmed.py`, and adding a second is a
policy decision about a specific institution -- not a configuration change.
"""


def owner_of(source_id: str) -> str:
    """The group a publisher belongs to; itself, when we do not know of one."""
    return _SAME_OWNER.get(source_id, source_id)


def independent_publishers(source_ids: Iterable[str]) -> set[str]:
    """
    The distinct *independent* publishers among these source ids.

    The set of distinct *owners*, which for most publishers is the publisher
    itself. Routing every independence question through this function rather than
    through `set(source_ids)` at the call sites is the whole reason extending the
    ownership map is a one-line change.

    >>> sorted(independent_publishers(["channel24", "channel24", "ekattor_tv"]))
    ['channel24', 'ekattor_tv']
    >>> sorted(independent_publishers(["dhaka_tribune", "bangla_tribune"]))
    ['tribune_group']
    """
    return {owner_of(s) for s in source_ids}


def is_confirmable(source_ids: Iterable[str], *, minimum: int) -> bool:
    """
    Would these sources justify `status = 'confirmed'`?

    `minimum` is passed in rather than read from settings here, so that this module
    has no configuration dependency and the threshold is visible at the call site.
    """
    return len(independent_publishers(source_ids)) >= minimum


# ---------------------------------------------------------------------------
# Weight
# ---------------------------------------------------------------------------

UNCONFIRMED_WEIGHT: Final[float] = 0.6
"""
What one publisher's unverified account is worth, relative to a corroborated one.

0.6, and the number is a judgement rather than a measurement — so it is one
constant in one place, with the reasoning attached, instead of a literal sprinkled
through the routing service.

The reasoning: it has to be well below 1.0, or "we verify before we publish" is
decoration. It has to be well above 0.0, or we have suppressed the early signal
that is the entire argument for reading news in the first place — the concept
document's worked example turns on a fire being known from one source before it is
corroborated. 0.6 keeps a single-source fire outranking a corroborated minor
delay, which is the ordering a traveller actually wants.

**Revisit this with D05's precision number**, not by taste. If single-source flags
turn out to be right 90% of the time, 0.6 is too harsh.
"""


def confidence(status: str, source_ids: Iterable[str] = ()) -> float:
    """
    How much of a flag's severity should count in a decision, 0-1.

    * `confirmed`   → 1.0. Two independent publishers agree.
    * `unconfirmed` → `UNCONFIRMED_WEIGHT`, unless an authoritative publisher is
      among its sources, in which case 1.0. See `AUTHORITATIVE_PUBLISHERS`.
    * anything else → 0.0. `expired` and `rejected` are not served at all; if one
      ever reaches a decision path, it should contribute nothing rather than
      quietly contributing fully.

    `source_ids` is optional and defaults to empty, which reproduces the original
    behaviour exactly. That default is deliberate: community clusters pass no
    publishers because they have none -- a cluster is user reports, and nothing
    about an official police release should change what a resident's report is
    worth.

    >>> confidence("unconfirmed")
    0.6
    >>> confidence("unconfirmed", ["dmp_news"])
    1.0
    >>> confidence("expired", ["dmp_news"])
    0.0
    """
    if status == "confirmed":
        return 1.0
    if status == "unconfirmed":
        if any(source_id in AUTHORITATIVE_PUBLISHERS for source_id in source_ids):
            return 1.0
        return UNCONFIRMED_WEIGHT
    return 0.0
