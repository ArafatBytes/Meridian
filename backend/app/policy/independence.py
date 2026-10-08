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
copy, currently count as two sources.** `_SAME_OWNER` below is the seam it plugs
into — populate it and `independent_publishers()` collapses them with no other
change. It is empty today because guessing Bangladeshi media ownership from
memory would be worse than admitting the gap.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

__all__ = [
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
    # EMPTY ON PURPOSE. See the module docstring: the ownership map is the Track B
    # half of S15's independence check. A publisher absent from this map is its own
    # owner, which is the permissive reading — so filling this in can only ever
    # *reduce* the number of flags we are willing to confirm, never increase it.
    #
    # When it is filled in, two entries sharing a value stop corroborating each
    # other. Nothing else needs to change.
}


def owner_of(source_id: str) -> str:
    """The group a publisher belongs to; itself, when we do not know of one."""
    return _SAME_OWNER.get(source_id, source_id)


def independent_publishers(source_ids: Iterable[str]) -> set[str]:
    """
    The distinct *independent* publishers among these source ids.

    Today that is the set of distinct owners, and since `_SAME_OWNER` is empty it is
    the set of distinct `source_id`s. Routing every independence question through
    this function rather than through `set(source_ids)` at the call sites is the
    whole reason filling in the ownership map later is a one-line change.

    >>> sorted(independent_publishers(["channel24", "channel24", "ekattor_tv"]))
    ['channel24', 'ekattor_tv']
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


def confidence(status: str) -> float:
    """
    How much of a flag's severity should count in a decision, 0-1.

    * `confirmed`   → 1.0. Two independent publishers agree.
    * `unconfirmed` → `UNCONFIRMED_WEIGHT`. Published, and discounted.
    * anything else → 0.0. `expired` and `rejected` are not served at all; if one
      ever reaches a decision path, it should contribute nothing rather than
      quietly contributing fully.
    """
    if status == "confirmed":
        return 1.0
    if status == "unconfirmed":
        return UNCONFIRMED_WEIGHT
    return 0.0
