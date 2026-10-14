"""
Attributed framing — the single writer of user-facing *news crime* text.

The third publishing vocabulary in this system, and the one that needs the most
care, because it is the only one that says the word "robbery" out loud.

    risk_flags            the product's own claim about movement.  framing.py
    community_clusters    a count of independent user reports.     community.py
    news_crime_incidents  what a named publisher reported.         THIS MODULE

---

## Why this is not a framing.py violation, and not a loophole either

`framing.py` bans `robbery`, `theft`, `mugging`, `snatching`, `harassment` and
twenty more, and says exactly why:

    "a user filing a report chooses a category, and the product repeats their word
     back to them on their own report. A risk flag is the product's own published
     claim about a place, and it does not get to say any of this."

Read that sentence closely: the ban is on **the product's own claim**, not on the
vocabulary. The same file already carves out the case where the product repeats
somebody else's word — a user's own category, on that user's own report.

This module is the second such case, and a stronger one. *The Daily Star reported a
robbery in Pallabi* is a fact about a published article. It is checkable, it is
attributable, it carries a URL, and the product is not the one asserting it. What
would be a violation is dropping the attribution and saying *there was a robbery in
Pallabi* — or worse, *Pallabi is dangerous*. The first is a claim this product has
no standing to make; the second is the characterisation the whole framing policy
exists to prevent.

So the guard here is not a weaker version of `assert_mobility_safe`. It is a
different shape:

* **A positive requirement.** `assert_attribution_safe` *rejects a statement that
  does not name its publisher.* No other guard in this codebase requires something
  to be present. It is the requirement that makes the crime vocabulary admissible,
  so it is not optional and it is checked first.
* **A ban on characterising the place**, which is where the real danger is. The
  category is a fact about an article; `dangerous`, `notorious`, `hotspot`,
  `crime-ridden`, `avoid` are judgements about a neighbourhood and its residents,
  and this product makes none of them.
* **A ban on naming anyone**, inherited verbatim from `framing._NAMED_GROUPS` plus
  a check against the article's own people. A crime report names suspects and
  victims; a map pin never does.

## What a statement may say

A category, who reported it, and how long ago:

    Robbery reported by Prothom Alo, 2 days ago
    Harassment reported by Dhaka Tribune and 2 others, yesterday

That is the whole grammar. There is no free text path, exactly as in `framing.py`,
and `tests/invariants/test_news_crime_is_attributed.py` asserts that nothing else
in the codebase writes `news_crime_incidents.statement`.

## One publisher is enough to publish, and is not enough to look certain

The owner's decision, 2026-10-14: *"news-sourced crime gets published because they
are coming from news which are verified."* That is a defensible premise — a named
outlet with an editor and a masthead is a different object from an anonymous post,
and this pipeline has never read anonymous posts.

It is not a reason to abandon corroboration, so the existing rule is applied rather
than waived: one publisher publishes at `PROVISIONAL_WEIGHT`, two or more
independent publishers at `CORROBORATED_WEIGHT`, and the statement says which by
naming the other outlets. The same arithmetic as `community.py`, for the same
reason — an account that several newsrooms reached independently is worth more than
one, and the surface should say so rather than flatten the difference.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Final

from app.policy.framing import NAMED_GROUPS, FramingViolation

__all__ = [
    "CORROBORATED_WEIGHT",
    "MAX_PUBLISHERS_NAMED",
    "MAX_STATEMENT_LENGTH",
    "MIN_PUBLISHERS_TO_CORROBORATE",
    "NEWS_CRIME_HALF_LIFE_HOURS",
    "PROVISIONAL_WEIGHT",
    "AttributionViolation",
    "assert_attribution_safe",
    "find_banned_terms",
    "radius_for",
    "severity_for",
    "to_attributed_statement",
]


class AttributionViolation(FramingViolation):
    """
    Raised when a candidate statement is not publishable as news-crime text.

    A subclass of `FramingViolation` on purpose: a caller that already refuses to
    publish on a framing failure refuses on this one too, without being changed and
    without knowing this module exists.
    """


# ---------------------------------------------------------------------------
# The categories, and what each is worth
# ---------------------------------------------------------------------------

CATEGORY_NOUNS: Final[dict[str, str]] = {
    # `crime_reports.category` verbatim, so one vocabulary covers a user's own
    # report and a published one. `other` becomes "Incident" rather than "Other
    # crime": the product does not need to assert that an unclassified event was a
    # crime at all, and "Incident reported by X" is both weaker and truer.
    "theft": "Theft",
    "assault": "Assault",
    "harassment": "Harassment",
    "vandalism": "Vandalism",
    "burglary": "Burglary",
    "robbery": "Robbery",
    "fraud": "Fraud",
    "other": "Incident",
}

_SEVERITY: Final[dict[str, float]] = {
    # 0-100, decayed on read like every other surface. These are judgements about
    # how much a traveller's route choice should move, NOT about how serious the
    # crime is — the two come apart, and conflating them is how a product like this
    # starts ranking neighbourhoods.
    #
    # Robbery and assault are street crimes against a person in transit, which is
    # precisely the situation this app is consulted in, so they weigh most.
    "robbery": 60.0,
    "assault": 58.0,
    # Harassment weighs with the violent group rather than the property group. It is
    # a street offence against a person on foot, it is the one many users are
    # actually navigating around, and filing it with vandalism would quietly encode
    # that it matters less.
    "harassment": 55.0,
    # Property crime against premises, not against someone passing. Lower, because
    # a burgled shop changes a route far less than a mugging on the same corner.
    "burglary": 35.0,
    "theft": 38.0,
    "vandalism": 25.0,
    # Fraud is not a property-based risk to a traveller at all. It is kept
    # publishable for completeness and weighted so it barely moves a route.
    "fraud": 10.0,
    "other": 30.0,
}

_RADIUS_M: Final[dict[str, int]] = {
    # How far from the named place the report is taken to say anything. Narrow:
    # a street crime is a corner, not a neighbourhood, and a wide radius is how a
    # single incident turns into an area label — the thing §9 forbids.
    "robbery": 250,
    "assault": 250,
    "harassment": 250,
    "theft": 250,
    "burglary": 200,
    "vandalism": 200,
    "fraud": 150,
    "other": 250,
}

NEWS_CRIME_HALF_LIFE_HOURS: Final[float] = 120.0
"""
Five days.

Between the two neighbours in `scoring/kinds.py` and deliberately so: a road
accident is one hour because the queue drains, and a chronic blackspot is ninety
days because it is a property of the place rather than an event. A reported crime
is an event, but one whose bearing on a route outlives the night — "there was a
mugging on this corner last week" is still worth knowing, and "last month" is not.

Five days also means a single incident is below a tenth of its initial weight
inside three weeks with no further reports, which is what stops the map silting up
into exactly the permanent-area-label the concept document rules out.
"""

MIN_PUBLISHERS_TO_CORROBORATE: Final[int] = 2
PROVISIONAL_WEIGHT: Final[float] = 0.35
CORROBORATED_WEIGHT: Final[float] = 0.7
"""
Mirrors `community.py`'s pair, slightly higher at both ends.

A named newsroom with an editor is a stronger single claim than one anonymous user
report, which is the owner's premise and is a fair one. It is still a single claim,
so it does not reach the weight of several independent ones.
"""

MAX_PUBLISHERS_NAMED: Final[int] = 2
"""Beyond this the statement says "and N others", to stay inside the length cap."""

MAX_STATEMENT_LENGTH: Final[int] = 160


def severity_for(category: str) -> float:
    return _SEVERITY.get(category, _SEVERITY["other"])


def radius_for(category: str) -> int:
    return _RADIUS_M.get(category, _RADIUS_M["other"])


def weight_for(publisher_count: int) -> float:
    """How much a route-scoring pass should let this incident move a score."""
    return (
        CORROBORATED_WEIGHT
        if publisher_count >= MIN_PUBLISHERS_TO_CORROBORATE
        else PROVISIONAL_WEIGHT
    )


# ---------------------------------------------------------------------------
# The banned vocabulary — different from framing.py's, and narrower on purpose
# ---------------------------------------------------------------------------

_PLACE_JUDGMENT_TERMS: Final[frozenset[str]] = frozenset(
    {
        # Characterisations of a PLACE. These are the ones that matter here,
        # because the crime noun itself is admissible and these are what turn a
        # cited report into an area label.
        "dangerous",
        "danger",
        "unsafe",
        "risky",
        "hazardous",
        "lawless",
        "notorious",
        "infamous",
        "hotspot",
        "blackspot",
        "crime-ridden",
        "ridden",
        "plagued",
        "rampant",
        "epidemic",
        "wave",
        "spree",
        "avoid",
        "beware",
        "warning",
        "no-go",
        "slum",
        "ghetto",
        # Second person. A statement that addresses the reader is advice, and this
        # product cites reports rather than advising anyone where not to walk.
        "you",
        "your",
    }
)

_BANNED_BANGLA: Final[frozenset[str]] = frozenset(
    {
        "বিপজ্জনক",  # dangerous
        "অনিরাপদ",  # unsafe
        "এড়িয়ে",  # avoid
        "কুখ্যাত",  # notorious
        "আওয়ামী",
        "বিএনপি",
        "জামায়াত",
        "হিন্দু",
        "মুসলিম",
    }
)

BANNED_TERMS: Final[frozenset[str]] = _PLACE_JUDGMENT_TERMS | NAMED_GROUPS | _BANNED_BANGLA

_ASCII_TERMS: Final[tuple[str, ...]] = tuple(sorted(t for t in BANNED_TERMS if t.isascii()))
_NON_ASCII_TERMS: Final[tuple[str, ...]] = tuple(sorted(t for t in BANNED_TERMS if not t.isascii()))
_ASCII_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in _ASCII_TERMS) + r")(?![A-Za-z])",
    re.IGNORECASE,
)

_ATTRIBUTION_MARKER: Final[str] = " reported by "


def find_banned_terms(text: str) -> list[str]:
    """Every banned term present in `text`, lowercased and sorted."""
    hits: set[str] = {m.group(1).lower() for m in _ASCII_PATTERN.finditer(text)}
    hits.update(term for term in _NON_ASCII_TERMS if term in text)
    return sorted(hits)


def assert_attribution_safe(text: str) -> None:
    """
    Raise `AttributionViolation` unless `text` is publishable as news-crime text.

    The attribution check runs **first**, and that ordering is the policy: the
    crime vocabulary below is only admissible *because* the sentence says who
    reported it, so a statement missing its publisher is rejected before anything
    else is even looked at.
    """
    if not text or not text.strip():
        raise AttributionViolation("news crime statement is empty")

    if _ATTRIBUTION_MARKER not in text:
        raise AttributionViolation(
            "news crime statement does not name a publisher: without attribution "
            "this is the product asserting a crime happened, which it has no "
            f"standing to do. Expected {_ATTRIBUTION_MARKER!r} in {text!r}"
        )

    if len(text) > MAX_STATEMENT_LENGTH:
        raise AttributionViolation(
            f"news crime statement is {len(text)} characters; "
            f"the limit is {MAX_STATEMENT_LENGTH}"
        )

    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        raise AttributionViolation(
            "news crime statement contains a URL; sources belong in the sources column"
        )

    banned = find_banned_terms(text)
    if banned:
        raise AttributionViolation(
            f"news crime statement uses banned term(s) {banned}: the category is "
            f"admissible because it is attributed, but characterising the place or "
            f"naming a group is not. In {text!r}"
        )


# ---------------------------------------------------------------------------
# The only producer of the published string
# ---------------------------------------------------------------------------


def _recency(observed_at: datetime, now: datetime) -> str:
    """`today`, `yesterday`, or `N days ago`. Never an exact time."""
    days = (now.date() - observed_at.date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def _publishers(names: list[str]) -> str:
    """`Prothom Alo`, `Prothom Alo and Jugantor`, `Prothom Alo and 2 others`."""
    unique = [n for n in dict.fromkeys(name.strip() for name in names) if n]
    if not unique:
        raise AttributionViolation("no publisher to attribute this report to")
    if len(unique) == 1:
        return unique[0]
    if len(unique) <= MAX_PUBLISHERS_NAMED:
        return " and ".join(unique)
    return f"{unique[0]} and {len(unique) - 1} others"


def to_attributed_statement(
    *,
    category: str,
    publishers: list[str],
    observed_at: datetime,
    now: datetime,
) -> str:
    """
    The **only** function that may produce `news_crime_incidents.statement`.

    Template-driven, like `framing.to_mobility_statement`, and for the same reason:
    there is no path through it that emits free text, so no model output and no
    article prose can reach a map pin. The extraction model's own words go to
    `extracted_incidents.summary_en` and stay there.

    >>> from datetime import UTC, datetime
    >>> to_attributed_statement(
    ...     category="robbery",
    ...     publishers=["Prothom Alo"],
    ...     observed_at=datetime(2026, 10, 12, tzinfo=UTC),
    ...     now=datetime(2026, 10, 14, tzinfo=UTC),
    ... )
    'Robbery reported by Prothom Alo, 2 days ago'
    """
    noun = CATEGORY_NOUNS.get(category, CATEGORY_NOUNS["other"])
    statement = (
        f"{noun}{_ATTRIBUTION_MARKER}{_publishers(publishers)}, "
        f"{_recency(observed_at, now)}"
    )
    # The guard runs on this module's own output, so the template cannot drift
    # either. Same arrangement as framing.py, and the same reason: the pressure to
    # write a more vivid sentence arrives later, from someone who did not read this.
    assert_attribution_safe(statement)
    return statement


def expires_after(observed_at: datetime) -> datetime:
    """When this incident stops being served at all. Ten half-lives, as elsewhere."""
    return observed_at + timedelta(hours=NEWS_CRIME_HALF_LIFE_HOURS * 10)
