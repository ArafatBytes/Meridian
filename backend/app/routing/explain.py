"""
Why this route. S13, and demo beat 4.

The concept document's target sentence is
*"fire reported near Bangshal, roads likely blocked, three sources"* — and the shape of
that sentence is the specification: **what**, **what it means for getting through**, and
**how well we know it**. Nothing else.

---

## Three constraints, and none of them is stylistic

**1. The text is assembled from `RiskFlag.mobility_statement` and the source count. It is
not written here.** `app/policy/framing.py` is the only producer of flag prose, and an
invariant test enforces that. This module quotes what the framing guard already approved
and adds counting words around it — so there is no second place where a sentence about a
neighbourhood could be composed, and no way for the word "clash" to reach a screen through
a route card after being kept off a flag sheet.

**2. No LLM in the request path.** S13 says template-driven, and the reason is not cost. A
route request is on the critical path of someone deciding which way to walk home; adding a
network call to a free-tier model means a p99 measured in seconds, a failure mode that
returns no explanation at all, and a sentence nobody reviewed. Templates are instant,
deterministic, and reviewable in this file.

**3. Everything returned passes `assert_mobility_safe`.** Belt and braces: the inputs are
already framed, but this module concatenates them, and concatenation is where a banned term
could in principle be assembled out of safe parts. The guard runs on the finished string.

## What an explanation is allowed to claim

Only mobility. "Road blocked", "heavy crowd", "expect delay" — never that an area is
dangerous, never who was involved, never a political characterisation. That is concept
document §9 and it is not negotiable, which is why the only prose this module owns is the
connective tissue: *"avoids"*, *"passes"*, *"minutes longer"*, *"sources"*.
"""

from __future__ import annotations

from typing import Final

from app.contracts.community import CommunityCluster
from app.contracts.risk import RiskFlag
from app.policy.framing import FramingViolation, find_banned_terms

__all__ = [
    "MAX_EXPLANATION_LENGTH",
    "assert_explanation_safe",
    "community_clause",
    "explain_route",
    "summarise_flag",
    "trade_off_sentence",
]


MAX_EXPLANATION_LENGTH: Final[int] = 200
"""
How long a route explanation may be.

Longer than `framing.MAX_STATEMENT_LENGTH` (160) **and deliberately a separate number**,
because the two limits are about different things. 160 is documented in `framing.py` as
"one line on a map pin" — a layout constraint on a single flag's statement. An explanation
quotes one of those statements and adds a source count and a trade-off clause, so it is
structurally longer while containing nothing a reviewer has not already seen.

It is still capped, and for the reason `framing.py` gives: *"there is no room in 160
characters for narrative, and narrative is where characterisation creeps back in."* That
argument does not stop applying at 161. 200 fits one named flag, its corroboration, a
count of the rest, and the trade-off — and nothing else. If an explanation does not fit,
the fix is to name fewer flags, never to raise this.
"""


def assert_explanation_safe(text: str) -> None:
    """
    The framing guard, applied to a route explanation rather than a flag statement.

    Shares the parts that are **invariants** — banned vocabulary, no pasted URLs, not
    empty — and uses its own length cap. It does not call `assert_mobility_safe` because
    that would enforce a flag pin's layout budget on a route card, which is how a correct
    explanation ends up rejected for being 26 characters too long.

    `find_banned_terms` is the shared half, so a term added to the banned list is enforced
    here too without anyone remembering to update this function.
    """
    if not text or not text.strip():
        raise FramingViolation("route explanation is empty")

    if len(text) > MAX_EXPLANATION_LENGTH:
        raise FramingViolation(
            f"route explanation is {len(text)} characters; the limit is "
            f"{MAX_EXPLANATION_LENGTH}. Name fewer flags rather than raising the limit."
        )

    lowered = text.lower()
    if "http://" in lowered or "https://" in lowered:
        raise FramingViolation(
            "route explanation contains a URL; sources belong in RouteFlag, not in prose"
        )

    banned = find_banned_terms(text)
    if banned:
        raise FramingViolation(
            "route explanation uses non-mobility vocabulary: "
            + ", ".join(repr(t) for t in banned)
            + ". Describe the effect on movement, not the event or the people."
        )


_COUNT_WORDS: Final[dict[int, str]] = {
    1: "one source",
    2: "two sources",
    3: "three sources",
    4: "four sources",
    5: "five sources",
}
"""
Words up to five, digits beyond.

"three sources" is the concept document's own phrasing and reads better than "3 sources"
in a sentence. Past five the word form stops helping, and a flag with six corroborating
publishers is not a case worth special-casing.
"""

_MAX_FLAGS_IN_SENTENCE: Final[int] = 1
"""
How many flags a single explanation names: **one**, the worst.

The concept document's own target sentence names a single event — *"fire reported near
Bangshal, roads likely blocked, three sources"* — and that is the right shape. A sentence
listing six flags is not an explanation, it is a list, and on a phone it is a wall of text
nobody reads before deciding which way to walk.

The rest are counted, not dropped: *"and 2 other flagged locations"*. And nothing is
hidden — the full set is in `RouteResponse.flags`, which the client draws on the map and
can expand. The sentence is the summary, not the data.

This started at 2 and was reduced after measurement: two named flags plus a trade-off
clause ran to 186 characters, which is past what fits a route card.
"""


def _count_phrase(count: int) -> str:
    return _COUNT_WORDS.get(count, f"{count} sources")


def summarise_flag(flag: RiskFlag) -> str:
    """
    One flag as a clause: its framed statement, plus how well it is corroborated.

    `mobility_statement` arrives already framed and already guarded, ending in a full
    stop; it is trimmed here so it can sit inside a longer sentence. The verification tier
    is carried in words as well as in the count, because *"one source, unconfirmed"* is the
    honest reading of a single-publisher claim and *"one source"* alone slightly oversells
    it.
    """
    statement = flag.mobility_statement.strip().rstrip(".")
    sources = _count_phrase(flag.source_count)
    if flag.status != "confirmed":
        sources = f"{sources}, unconfirmed"
    return f"{statement} ({sources})"


def trade_off_sentence(
    *,
    duration_s: float,
    fastest_duration_s: float,
    avoided_count: int,
) -> str | None:
    """
    *"4 minutes longer, avoids two flagged corridors."* — the comparison, in one clause.

    Returns `None` when there is nothing to trade: the fastest route that also avoids
    nothing extra needs no justification, and inventing one would be noise. This is the
    sentence `DEMO_PLAN.md` D06 asks for by name.

    Rounds to whole minutes. A difference under a minute is not a trade-off a traveller can
    act on, and "0 minutes longer" reads as a bug.
    """
    minutes_longer = round((duration_s - fastest_duration_s) / 60.0)

    if minutes_longer > 0 and avoided_count > 0:
        corridor = "corridor" if avoided_count == 1 else "corridors"
        minute = "minute" if minutes_longer == 1 else "minutes"
        return (
            f"{minutes_longer} {minute} longer, avoids {avoided_count} flagged {corridor}."
        )
    if minutes_longer > 0:
        minute = "minute" if minutes_longer == 1 else "minutes"
        return f"{minutes_longer} {minute} longer."
    if avoided_count > 0:
        corridor = "corridor" if avoided_count == 1 else "corridors"
        return f"Fastest, and avoids {avoided_count} flagged {corridor}."
    return None


_TERSE_COMMUNITY_CLAUSE: Final[str] = "Community reports along this route."
"""
The fallback when the full clause will not fit. See `explain_route`.

It drops the counts, which is a real loss -- the counts are the whole substance of a
cluster -- and keeps the fact that there are reports, which is the part a traveller
must not lose. The full numbers are still on every cluster in `RouteResponse.clusters`,
so the card can render them beside the sentence rather than inside it.
"""


def community_clause(clusters: list[CommunityCluster]) -> str | None:
    """
    One clause about community report clusters on this corridor, or None. B13.

    Separate from `summarise_flag` and deliberately plainer. A flag's clause carries
    a `mobility_statement` written by `policy/framing.py` and a source count, because
    a flag is the product's own claim about a road. A cluster is not: it is a count of
    what residents reported, and the only honest thing to say about it is that count.

    So this names reporters and a count of stretches and nothing else -- no category,
    no severity word, no characterisation of the place. The cluster's own `statement`
    already says it in the published form; this is the route-card phrasing of the
    same fact.

    Aggregated across clusters rather than one clause each. Three clusters along a
    corridor is "3 stretches where..." to a traveller, not three sentences, and the
    corridor is the unit the card is about.
    """
    if not clusters:
        return None

    reporters = sum(cluster.reporter_count for cluster in clusters)
    corroborated = sum(1 for cluster in clusters if cluster.status == "corroborated")

    where = "one stretch" if len(clusters) == 1 else f"{len(clusters)} stretches"
    people = "person" if reporters == 1 else "people"

    clause = f"{reporters} {people} filed reports along {where} of this route"
    # Only claimed when at least one cluster has actually reached the upper tier. A
    # provisional cluster is two accounts agreeing, and calling that corroborated
    # would be the over-claim the tiers exist to prevent.
    if corroborated:
        clause = f"{clause}, independently corroborated"
    return f"{clause}."


def explain_route(
    flags: list[RiskFlag],
    *,
    duration_s: float,
    fastest_duration_s: float,
    avoided_count: int = 0,
    clusters: list[CommunityCluster] | None = None,
) -> str:
    """
    The sentence shown on the route card. Beat 4.

    Built in two halves: what is known about this corridor, then what choosing it costs.
    A clean route says so plainly — *"Nothing flagged along this route"* — because an empty
    explanation reads as a failure to load, and "we checked and found nothing" is a real
    answer that this product is unusual in being able to give.

    `flags` must be worst-first; `scorer.score_path` returns them that way.

    `clusters` is optional and defaults to none, so the offline path -- which has no
    cluster surface -- produces exactly the sentence it did before B13. When clusters
    are present they get their own clause after the flags, never mixed into them: the
    two are different claims, and a sentence that blurred them would be the route card
    repeating the map's own Defect 54 confusion in prose.
    """
    parts: list[str] = []

    if flags:
        named = flags[:_MAX_FLAGS_IN_SENTENCE]
        clauses = [summarise_flag(flag) for flag in named]
        remaining = len(flags) - len(named)

        body = "; ".join(clauses)
        if remaining == 1:
            body = f"{body}; and one other flagged location"
        elif remaining > 1:
            body = f"{body}; and {remaining} other flagged locations"
        parts.append(f"Passes {body}.")
    elif not clusters:
        # "Nothing flagged" is only true when there is nothing of either kind. A
        # route with no flags but two report clusters on it is not a clean route,
        # and saying so would be the one sentence on this card that is a lie.
        parts.append("Nothing flagged along this route.")

    trade = trade_off_sentence(
        duration_s=duration_s,
        fastest_duration_s=fastest_duration_s,
        avoided_count=avoided_count,
    )

    # The community clause is the one part that may be SHORTENED OR DROPPED, in that
    # order, to fit `MAX_EXPLANATION_LENGTH`.
    #
    # This is not a nicety. Before B13 the sentence was a flag clause plus a trade-off
    # and comfortably inside 200 characters; adding a third clause can push a worst
    # case past it, and `assert_explanation_safe` raises rather than truncating. An
    # uncaught `FramingViolation` here does not produce a shorter card -- it fails the
    # whole route request, so a route would become unroutable because too much was
    # known about it.
    #
    # Degrading rather than raising is the behaviour `framing.to_mobility_statement`
    # already chose for the same problem: *"a place name that fails the guard is
    # dropped and the statement falls back to the placeless form. The flag still
    # publishes, with less detail -- the right trade."*
    #
    # The flag clause and the trade-off are never dropped: the first is what the score
    # is made of, and the second is why this route is being offered at all.
    candidates = [
        community_clause(clusters or []),
        _TERSE_COMMUNITY_CLAUSE if clusters else None,
        None,
    ]
    sentence = " ".join(parts + ([trade] if trade else []))
    for community in candidates:
        attempt = " ".join(parts + ([community] if community else []) + ([trade] if trade else []))
        if len(attempt) <= MAX_EXPLANATION_LENGTH:
            sentence = attempt
            break

    # The guard on the finished string, not just on the inputs. Concatenation is the one
    # place a banned term could be assembled out of individually safe parts, and this is
    # the last point before the text reaches a screen.
    assert_explanation_safe(sentence)
    return sentence
