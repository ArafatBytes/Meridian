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
    "VETTED_PUBLISHERS",
    "confidence",
    "independent_publishers",
    "is_confirmable",
    "is_vetted",
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

VETTED_PUBLISHERS: Final[frozenset[str]] = frozenset(
    {
        # Television, chosen 2026-10-08.
        "ekattor_tv",
        "independent_tv",
        "channel24",
        # Newspapers, chosen 2026-10-14.
        "prothom_alo",
        "jugantor",
        "samakal",
        "ittefaq",
        "bangla_tribune",
        "dhaka_tribune",
        # The institutional tier, 2026-10-15.
        "dmp_news",
    }
)
"""
The publishers whose word is enough, on its own, for `status = 'confirmed'`.

**This is the list in `app/ingestion/sources/__init__.py`, restated.** It is
restated rather than imported because importing `SOURCES` here would drag the
fetcher, `httpx` and every parser into the routing request path -- which reads
`confidence()` on every flag of every candidate route.
`tests/invariants/test_single_source_never_confirmed.py` asserts the two lists
match, so they cannot drift.

## Why one of these is enough, which was not always the rule

Until 2026-10-16 `confirmed` meant *two independent publishers agreed*, and
every flag built from one article was `unconfirmed` -- drawn as a hollow pin
with a question mark and scored at `UNCONFIRMED_WEIGHT` in routing.

That rule was written before anyone had decided which publishers the surface
would read. It treated every outlet as an anonymous claimant. In fact all ten
were chosen by hand against stated criteria, with the ten that failed recorded
by name and reason -- Prothom Alo, Channel 24 and the Dhaka Metropolitan Police
are not anonymous claimants, and a national newsroom does not invent a fire.

Measured on live data the day it changed: of 19 flags built from news, **15 had
a single source**. So the old rule left 79% of the live surface hollow and
discounted, including a Prothom Alo report of a fire.

## What this gives up, recorded because it is not nothing

A second independent newsroom was never only a check on honesty. It was the one
independent check on **our own extraction**: two newsrooms, read separately by
the model, landing on the same kind, place and six-hour window is evidence the
pipeline read both correctly. One source gives that up, and what remains against
a mis-extraction is `MIN_CONFIDENCE`, the gazetteer's refusal to guess a
location, and the mobility-impact filter -- all inside `live_risk.py`.

Rumour Guard keeps its job: merging four accounts of one fire into one flag is
what stops the map showing four fires, and `source_count` still counts
independent publishers. It no longer gates the badge.

## What `unconfirmed` still means

A **community report** -- a resident's account, with no newsroom behind it.
That is the distinction users most need drawn, and it is now the one the pin
style actually draws.

## Adding to this list is a policy decision

An entry here *increases* what a single source is worth, which is the direction
`_SAME_OWNER` cannot go. A publisher reaches this list by going through the
survey in `sources/__init__.py` -- robots.txt, a machine-readable listing,
body text in the HTML -- not by being added here.
"""


AUTHORITATIVE_PUBLISHERS: Final[frozenset[str]] = frozenset({"dmp_news"})
"""
Publishers that are the **primary record** of what they report, not a claim about it.

DMP News is the Dhaka Metropolitan Police's own outlet. When it says two muggers
were arrested in Uttara, that is the police's own account of their own action --
and a newspaper repeating it adds no independent verification, because the paper
got it from the release. Corroboration between a press release and its reprints is
agreement manufactured by syndication, which is the same hazard `_SAME_OWNER`
guards against wearing different clothes.

**Kept as a separate set from `VETTED_PUBLISHERS`, which now contains it.**

Since 2026-10-16 every vetted publisher is enough for `confirmed`, so this set
grants nothing `VETTED_PUBLISHERS` does not. It stays because the two say
different things and will diverge again the moment a non-vetted source is added:
`VETTED_PUBLISHERS` means *we chose this outlet and checked it*, while this means
*this body is the primary record of what it reports, so a newspaper repeating it
adds no independent verification*. Only the second is a reason to distrust
corroboration between a release and its reprints.

The history is worth keeping. On 15 Oct the owner asked for DMP to be
`confirmed` at one source; the database CHECK
`risk_flags_confirmed_needs_two_sources` made that impossible without a migration,
and weight was taken instead. On 16 Oct the question came back for the whole
publisher list, with the measurement that 79% of live flags were hollow, and the
CHECK was replaced by
`20261016150000__a_vetted_newsroom_is_confirmation.sql`.
"""


def is_vetted(source_ids: Iterable[str]) -> bool:
    """
    Is any of these a publisher we chose and checked?

    One is enough, which is the whole of the 2026-10-16 change. See
    `VETTED_PUBLISHERS`.

    >>> is_vetted(["prothom_alo"])
    True
    >>> is_vetted(["some_blog"])
    False
    >>> is_vetted([])
    False
    """
    return any(source_id in VETTED_PUBLISHERS for source_id in source_ids)


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

    True on **either** ground:

    * one of them is a vetted publisher -- a newsroom or institution we chose
      and checked (`VETTED_PUBLISHERS`); or
    * `minimum` or more *independent* publishers agree, which is the original
      rule and still the one that applies to anything not on that list.

    Keeping the second clause is not decoration. Community clusters and any
    future un-vetted source still reach `confirmed` only by corroboration, so
    the mechanism is there the moment something is read that was not hand-picked.

    `minimum` is passed in rather than read from settings here, so that this
    module has no configuration dependency and the threshold is visible at the
    call site.

    >>> is_confirmable(["prothom_alo"], minimum=2)
    True
    >>> is_confirmable(["some_blog"], minimum=2)
    False
    >>> is_confirmable(["some_blog", "another_blog"], minimum=2)
    True
    """
    ids = list(source_ids)
    if is_vetted(ids):
        return True
    return len(independent_publishers(ids)) >= minimum


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
        # Belt and braces. Since 2026-10-16 a vetted publisher's flag is promoted
        # to `confirmed` at write time, so this branch should not be reached for
        # one -- but a row written before that change, or one whose promotion was
        # refused by a constraint, must not be discounted as though a newsroom
        # were a rumour.
        if is_vetted(source_ids):
            return 1.0
        return UNCONFIRMED_WEIGHT
    return 0.0
