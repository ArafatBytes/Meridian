"""
Mobility framing — the single writer of user-facing flag text.

Concept document §9 commits to one thing above all others: Meridian describes
**effects on movement**, never people, politics, religion or safety. A procession
is a road that is blocked. A clash is a road that is impassable. The product does
not say who, and it does not claim anywhere is dangerous.

That commitment is worth nothing as an intention, because the pressure to break
it is constant and local: an LLM returns a vivid sentence, a fixture author types
something descriptive, a template gets improved at 1 a.m. So it is enforced
structurally instead:

1. `to_mobility_statement()` is the **only** function in the codebase that
   produces `RiskFlag.mobility_statement`. It is template-driven. There is no
   path through it that emits free text.
2. `assert_mobility_safe()` is a guard that rejects judgment vocabulary, event
   names carrying political weight, and any named group. It runs on the output of
   (1), so the templates cannot drift either.
3. `tests/invariants/test_no_flag_text_bypasses_framing.py` asserts both: that
   nothing else writes the field, and that every statement in the fixtures and in
   the database passes the guard.

**If this guard ever rejects something you wanted to publish, change what you
were publishing.** Shortening the banned list is how the invariant dies, and it
will be the cheapest-looking fix available at the time.
"""

import re
from typing import Final

from app.contracts.risk import IncidentKind, MobilityImpact


class FramingViolation(ValueError):
    """
    Raised when a candidate statement fails the guard.

    Deliberately an exception rather than a sanitising return value. A sanitiser
    would silently publish a half-fixed sentence; an exception stops the write
    and names the term responsible.
    """


# ---------------------------------------------------------------------------
# The banned vocabulary
# ---------------------------------------------------------------------------
# Three groups, kept apart because the reason each is here differs and a future
# reader will want to know which reason applies.

_JUDGMENT_TERMS: Final[frozenset[str]] = frozenset(
    {
        # Safety characterisations. The product reports mobility, not safety.
        "dangerous",
        "danger",
        "unsafe",
        "risky",
        "hazardous",
        "lawless",
        # Crime and violence vocabulary. A flag is not an accusation.
        #
        # Note that several of these ARE valid `crime_reports.category` values.
        # That is not a contradiction: a user filing a report chooses a category,
        # and the product repeats their word back to them on their own report. A
        # *risk flag* is the product's own published claim about a place, and it
        # does not get to say any of this.
        "crime",
        "criminal",
        "robbery",
        "robber",
        "theft",
        "thief",
        "burglary",
        "snatching",
        "mugging",
        "dacoity",
        "harassment",
        "kidnapping",
        "abduction",
        "rape",
        "shooting",
        "gunfire",
        "bomb",
        "violent",
        "violence",
        "attack",
        "attacked",
        "assault",
        "murder",
        "killed",
        "stabbed",
        "looting",
        "loot",
        "arson",
        "mob",
        "vandal",
        "vandalism",
        "terrorist",
        "terrorism",
        "extremist",
        "militant",
    }
)

_POLITICAL_EVENT_TERMS: Final[frozenset[str]] = frozenset(
    {
        # These name an event by its politics. The mobility consequence is the
        # part the product is entitled to publish: "road blocked", not "hartal".
        "hartal",
        "protest",
        "protester",
        "protesters",
        "demonstration",
        "demonstrator",
        "rally",
        "procession",
        "agitation",
        "clash",
        "clashes",
        "unrest",
        "riot",
        "riots",
        "curfew",
        "crackdown",
    }
)

_NAMED_GROUPS: Final[frozenset[str]] = frozenset(
    {
        # Parties, student wings, religious and ethnic identities. Naming any of
        # these in a mobility statement is outside the product's scope, and in
        # Bangladesh it is also the fastest route to being read as taking a side.
        "awami",
        "bnp",
        "jamaat",
        "shibir",
        "chhatra",
        "jatiya",
        "hefazat",
        "hindu",
        "muslim",
        "islamist",
        "christian",
        "buddhist",
        "ahmadiyya",
        "bihari",
        "rohingya",
        "chakma",
        "communal",
        "sectarian",
        "religious",
        "political",
        "opposition",
        "minority",
        "majority",
        "ethnic",
    }
)

_BANNED_BANGLA: Final[frozenset[str]] = frozenset(
    {
        "বিপজ্জনক",  # dangerous
        "অনিরাপদ",  # unsafe
        "অপরাধ",  # crime
        "সন্ত্রাস",  # terror
        "সংঘর্ষ",  # clash
        "হামলা",  # attack
        "হরতাল",  # hartal
        "মিছিল",  # procession, rally
        "বিক্ষোভ",  # protest
        "আওয়ামী",
        "বিএনপি",
        "জামায়াত",
        "হিন্দু",
        "মুসলিম",
    }
)

NAMED_GROUPS: Final[frozenset[str]] = _NAMED_GROUPS
"""
Exported because `policy/attribution.py` reuses it verbatim.

That module publishes news-sourced crime, so it deliberately does **not** inherit
`_JUDGMENT_TERMS` — the crime nouns are the thing it is allowed to say, once the
sentence names the publisher. The rule about never naming a party, a student wing
or a religious or ethnic identity is not relaxed anywhere, so it lives in one place
and both guards read it. One list, two policies.
"""

BANNED_TERMS: Final[frozenset[str]] = (
    _JUDGMENT_TERMS | _POLITICAL_EVENT_TERMS | _NAMED_GROUPS | _BANNED_BANGLA
)

MAX_STATEMENT_LENGTH: Final[int] = 160
"""
A mobility statement is one line on a map pin, not a paragraph. The cap is a
framing control as much as a layout one: there is no room in 160 characters for
narrative, and narrative is where characterisation creeps back in.
"""

# ASCII terms match on letter boundaries, so "mob" does not fire inside "mobile"
# and "loot" does not fire inside "Looters Road". Bangla terms match as plain
# substrings: the script has no case and takes agglutinative suffixes, so a
# boundary match would miss the inflected forms that actually appear in copy.
_ASCII_TERMS: Final[tuple[str, ...]] = tuple(sorted(t for t in BANNED_TERMS if t.isascii()))
_NON_ASCII_TERMS: Final[tuple[str, ...]] = tuple(sorted(t for t in BANNED_TERMS if not t.isascii()))
_ASCII_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in _ASCII_TERMS) + r")(?![A-Za-z])",
    re.IGNORECASE,
)


def find_banned_terms(text: str) -> list[str]:
    """
    Every banned term present in `text`, lowercased and sorted.

    Separate from `assert_mobility_safe` so tests and tooling can report *what*
    is wrong with a candidate string without catching an exception.
    """
    hits: set[str] = {m.group(1).lower() for m in _ASCII_PATTERN.finditer(text)}
    hits.update(term for term in _NON_ASCII_TERMS if term in text)
    return sorted(hits)


def assert_mobility_safe(text: str) -> None:
    """
    Raise `FramingViolation` unless `text` is publishable as flag text.

    Checks, in roughly the order each one actually fires:

    * the string is empty or only whitespace;
    * it is longer than `MAX_STATEMENT_LENGTH`;
    * it contains a URL, which means a source was pasted in rather than cited
      (sources belong in `RiskFlag.sources`);
    * it uses a banned term.
    """
    if not text or not text.strip():
        raise FramingViolation("mobility statement is empty")

    if len(text) > MAX_STATEMENT_LENGTH:
        raise FramingViolation(
            f"mobility statement is {len(text)} characters; the limit is {MAX_STATEMENT_LENGTH}"
        )

    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        raise FramingViolation(
            "mobility statement contains a URL; sources belong in RiskFlag.sources"
        )

    banned = find_banned_terms(text)
    if banned:
        raise FramingViolation(
            "mobility statement uses non-mobility vocabulary: "
            + ", ".join(repr(t) for t in banned)
            + ". Describe the effect on movement, not the event or the people."
        )


# ---------------------------------------------------------------------------
# The templates
# ---------------------------------------------------------------------------
# The entire expressive range of the product's flag text. Adding a sentence here
# is a deliberate act that shows up in a diff, which is the point.

_IMPACT_PHRASE: Final[dict[MobilityImpact, str]] = {
    MobilityImpact.ROAD_BLOCKED: "Road blocked",
    MobilityImpact.HEAVY_CROWD: "Heavy crowd",
    MobilityImpact.DELAY_LIKELY: "Delay likely",
    MobilityImpact.LANE_CLOSED: "Lane closed",
    MobilityImpact.IMPASSABLE: "Road impassable",
    MobilityImpact.NONE: "No road impact reported",
}

# A few kinds carry a mobility nuance worth one clause. Everything else gets the
# impact phrase alone, because a longer sentence is not a better one.
_KIND_QUALIFIER: Final[dict[IncidentKind, str]] = {
    IncidentKind.CHRONIC: ", reported repeatedly over time",
    IncidentKind.CONSTRUCTION: ", ongoing works",
    IncidentKind.WATERLOGGING: ", standing water",
    IncidentKind.UTILITY_OUTAGE: ", utility works",
}

_NO_PLACE: Final[str] = "in this area"


def to_mobility_statement(
    *,
    kind: IncidentKind,
    impact: MobilityImpact,
    place: str | None = None,
) -> str:
    """
    The one way to produce `RiskFlag.mobility_statement`.

    `place` is untrusted: it arrives from a news article or a gazetteer entry and
    may itself carry a banned term. Rather than raise and lose the flag, a place
    name that fails the guard is **dropped** and the statement falls back to the
    placeless form. The flag still publishes, with less detail — the right trade,
    because the alternatives are no flag at all or an unframed one.

    Always returns a string that passes `assert_mobility_safe`.
    """
    phrase = _IMPACT_PHRASE[impact]
    qualifier = _KIND_QUALIFIER.get(kind, "")

    def build(where: str) -> str:
        return f"{phrase} {where}{qualifier}."

    if place and place.strip():
        candidate = build(f"near {place.strip()}")
        try:
            assert_mobility_safe(candidate)
        except FramingViolation:
            pass  # The place name, not the template, is the problem. Fall through.
        else:
            return candidate

    statement = build(_NO_PLACE)
    # Templates are known-safe, so this is a regression guard rather than a
    # runtime branch: it fires only if the tables above are edited badly.
    assert_mobility_safe(statement)
    return statement
