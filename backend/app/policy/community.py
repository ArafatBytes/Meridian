"""
What a group of user reports is worth, and the only sentence it may say.

The user-report counterpart of `policy/independence.py`, and split from it for the
same reason that module is split from `agents/rumour_guard.py`: the agent decides
*which reports describe one pattern*, which is a geometry-and-time problem, and
this decides *whether several strangers agreeing means anything*, which is an
editorial one. They change for different reasons.

---

## The rule this module encodes

**A single report is never published.** Not held in a queue, not shown greyed
out — not published at all. It stays the author's own private record, which is
what it already was: it is their history, and the input to their GD draft.

What can be published is a *pattern*: several people, independently, reporting
incidents in the same small area inside the same window. That is the same
definition of "believable" this system already applies to news
(`agents/rumour_guard.py`), and it is applied here for the same reason — nobody
can verify that an incident occurred, so the only honest basis for publishing is
corroboration.

## Why the bar is higher than it is for news, and the weight lower

`risk_flags` confirms on **two independent publishers**. Two app accounts are not
two newspapers:

* a newspaper has an editor, a masthead and something to lose;
* an app account costs an email address.

So the thresholds here are one step stricter and the weights one step lower than
`independence.py`'s. A corroborated cluster is worth what an *unconfirmed* news
flag is worth (0.6) and no more. There is deliberately no path by which community
reports alone reach 1.0: that number means "independent editors agreed", and
letting crowd volume reach it would make the whole verification tier mean less.

## Weights, and the ordering they produce

| Evidence | Status | Weight |
|---|---|---|
| 1 reporter | not published | — |
| 2 independent reporters | `provisional` | 0.3 |
| 3+ independent reporters | `corroborated` | 0.6 |

With `severity_for()` below, three reporters produce an effective penalty of
50 × 0.6 = 30, against a live fire's 70 × 1.0 = 70. That ordering is the one a
traveller wants: a pattern of recent reports matters, and a fire that started an
hour ago matters more.

## The abuse surface, stated plainly

`DEMO_PLAN.md` B13 calls crowd verification *"an abuse surface"* and says not to
rush it. It is right, and the honest description of what is below is that it makes
manufacturing a cluster **expensive and auditable**, not impossible:

* `MIN_REPORTERS_TO_PUBLISH` reporters must be *distinct accounts*;
* one report per account per cluster counts, so volume from one person is worth
  nothing (`independent_reporters`);
* `MIN_ACCOUNT_AGE_HOURS` keeps an account registered after the fact from
  corroborating it, which is what makes a batch of throwaway signups useless;
* the `reports` array keeps a per-cluster pseudonym per contributing report, so a
  cluster can be re-derived and audited after the fact without this becoming a
  record of who reported what.

Three deliberate gaps, each with its seam named rather than implied:

1. **No phone verification gate.** `users.phone` and `users.is_verified` exist and
   `eligible_reporters()` is where that check goes. It is not wired because the
   registration flow does not verify a phone today, so requiring it would publish
   nothing at all.
2. **No proximity proof.** S29 asks for it. `push_devices.last_location` is the
   only position the server has, it is a single overwritten point, and demanding it
   would mean declining reports from anyone who filed from home. It is the right
   next tier and it is a privacy trade that should be made deliberately.
3. **No reporter reputation.** It needs ground truth about which past reports were
   real, and we have none.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from app.policy.framing import assert_mobility_safe

__all__ = [
    "CLUSTER_HALF_LIFE_HOURS",
    "CLUSTER_RADIUS_M",
    "CLUSTER_WINDOW",
    "CORROBORATED_WEIGHT",
    "ClusterStatus",
    "MIN_ACCOUNT_AGE_HOURS",
    "MIN_REPORTERS_TO_CORROBORATE",
    "MIN_REPORTERS_TO_PUBLISH",
    "PROVISIONAL_WEIGHT",
    "ReportFamily",
    "confidence",
    "eligible_reporters",
    "family_for_category",
    "independent_reporters",
    "severity_for",
    "status_for",
    "to_cluster_statement",
]


# ---------------------------------------------------------------------------
# Families: which reports are allowed to corroborate each other
# ---------------------------------------------------------------------------


class ReportFamily(StrEnum):
    """
    The grouping used to decide whether two reports describe one pattern.

    Coarser than `CrimeCategory` on purpose. Two people describing the same
    snatching will often file it under different categories — one picks `theft`,
    the other `robbery` — and treating those as different patterns is exactly the
    under-merging failure `rumour_guard.py` warns about: *"each stays unconfirmed
    forever, because corroboration that arrived was counted as a separate claim."*

    Coarser still would be worse. Folding a burglary into an assault would mean
    three unrelated incidents on one street corroborating each other, and a cluster
    that is the sum of everything that ever happened nearby says nothing.

    **This is never published.** It is the join key, and serving it would publish
    the category by another name — see `to_cluster_statement`.
    """

    VIOLENT = "violent"
    PROPERTY = "property"
    OTHER = "other"


_FAMILY_BY_CATEGORY: Final[Mapping[str, ReportFamily]] = {
    # Against a person.
    "assault": ReportFamily.VIOLENT,
    "harassment": ReportFamily.VIOLENT,
    # Against property, including the hybrid ones. `robbery` is force against a
    # person *for* property and could sit in either; it goes here because the
    # pattern a traveller cares about is "things get taken on this stretch", and
    # `theft` is the category most people pick for the same event.
    "robbery": ReportFamily.PROPERTY,
    "theft": ReportFamily.PROPERTY,
    "burglary": ReportFamily.PROPERTY,
    "vandalism": ReportFamily.PROPERTY,
    # `fraud` is deliberately NOT property. Fraud is not a property of a place --
    # it happens over a phone or a counter, and clustering it by location would
    # produce a map of where victims happened to be standing.
    "fraud": ReportFamily.OTHER,
    "other": ReportFamily.OTHER,
}


def family_for_category(category: str) -> ReportFamily:
    """
    The family a report category belongs to; `OTHER` for anything unrecognised.

    Permissive on an unknown category rather than raising: a category added to the
    database before it is added here should land in the family that corroborates
    least aggressively, not stop the agent.
    """
    return _FAMILY_BY_CATEGORY.get(category.strip().lower(), ReportFamily.OTHER)


# ---------------------------------------------------------------------------
# Geometry and time
# ---------------------------------------------------------------------------

CLUSTER_RADIUS_M: Final[int] = 200
"""
How close two reports must be to describe one pattern.

200 m is roughly a block and a half in Dhaka — a stretch of road a person would
describe as one place, and about the accuracy a phone's location has in a dense
area with tall buildings either side.

Wider stops meaning anything: at 1 km a cluster covers a neighbourhood, and
"somewhere in Dhanmondi" is the area label concept document section 9 forbids.
Narrower than the location error means two reports of one incident land in two
clusters and never corroborate.
"""

CLUSTER_WINDOW: Final[timedelta] = timedelta(days=14)
"""
How far apart two incidents may be and still be one pattern.

A fortnight, where `rumour_guard.DEDUP_WINDOW_HOURS` is hours. The difference is
deliberate and is the difference between the two things being measured: four
outlets covering one fire publish within hours of each other, so a week apart is a
different fire. Three muggings on one corner a week apart is not three unrelated
events — it *is* the pattern, and demanding they happen the same evening would
only ever cluster a crowd of witnesses to a single incident.

Paired with `CLUSTER_HALF_LIFE_HOURS` so a cluster serves for about as long as the
window that built it: a pattern that stops producing reports fades out rather than
standing on the map forever.
"""

CLUSTER_HALF_LIFE_HOURS: Final[float] = 72.0
"""
Three days, so a cluster at `severity_for(3)` is served for about ten days.

Between the event flags (1-8 hours) and the chronic layer (90 days), which is
where this object sits: it is not an incident and it is not a historical average.

The number is a judgement, and the thing it has to get right is that a cluster
**disappears on its own**. A corroborated group of reports that never expired would
be a permanent label on a street, which is the single output this product has
committed to never producing, and no amount of correct arithmetic elsewhere would
undo it. When this is tuned, it should be tuned *down*.
"""


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

MIN_REPORTERS_TO_PUBLISH: Final[int] = 2
"""
Below this, nothing is published. Mirrored by the
`community_clusters_needs_two_reporters` CHECK, which is what makes it true of
anything that ever writes to the table.
"""

MIN_REPORTERS_TO_CORROBORATE: Final[int] = 3
"""
Three independent accounts for the upper tier, against two publishers for a
confirmed news flag. See the module docstring: an account costs an email address.

Mirrored by `community_clusters_corroborated_needs_three`.
"""

MIN_ACCOUNT_AGE_HOURS: Final[float] = 24.0
"""
An account must have existed this long *before the incident it reports* to count.

This is the one control that makes a manufactured cluster expensive rather than
free. Without it, three throwaway signups corroborate anything in five minutes;
with it, they corroborate nothing that has already happened, and an attacker has
to decide a day in advance which corner to lie about.

Measured against `incident_date_time`, not against the filing time, for exactly
that reason — otherwise an attacker waits a day and the gate is a delay, not a
cost.

A real witness who installs the app *because* of what they just saw is refused by
this, and that is a real cost, honestly the most expensive thing in this module.
It is accepted because the alternative is a surface anyone can manufacture, and
because their report is still their own record and still feeds their GD draft.
"""


class ClusterStatus(StrEnum):
    """
    Mirrors `community_clusters_status_check`.

    Two live states, because there are two evidence tiers. `expired` and `removed`
    are terminal: the first is the sweep's doing, the second is the only human
    lever in the whole design (see the report_trust migration — the machine
    promotes, a human only demotes).
    """

    PROVISIONAL = "provisional"
    CORROBORATED = "corroborated"
    EXPIRED = "expired"
    REMOVED = "removed"


def status_for(reporter_count: int) -> ClusterStatus | None:
    """
    The status this many independent reporters earns, or `None` for "do not publish".

    `None` rather than a `hidden` status: a cluster that should not be published
    should not exist as a row, because a row is a thing a later query can forget to
    filter.
    """
    if reporter_count >= MIN_REPORTERS_TO_CORROBORATE:
        return ClusterStatus.CORROBORATED
    if reporter_count >= MIN_REPORTERS_TO_PUBLISH:
        return ClusterStatus.PROVISIONAL
    return None


# ---------------------------------------------------------------------------
# Weight
# ---------------------------------------------------------------------------

PROVISIONAL_WEIGHT: Final[float] = 0.3
"""
What two strangers agreeing is worth, relative to a corroborated news flag.

Half of `independence.UNCONFIRMED_WEIGHT`, which is the comparison that sets it:
one newspaper reporting a fire is better evidence than two app accounts reporting
a theft, and the number has to say so.

Above zero because two independent people is genuinely a signal, and a surface
that discards it has thrown away the only thing user reports are for.
"""

CORROBORATED_WEIGHT: Final[float] = 0.6
"""
Three independent reporters: exactly `independence.UNCONFIRMED_WEIGHT`.

Deliberately equal rather than higher. A pattern three strangers agree on is worth
about what one edited newspaper account is worth — and the ceiling is the point.
There is no community-only route to 1.0, because 1.0 means independent editors
agreed. If this is ever raised, the thing to raise first is the threshold.
"""


def confidence(status: str) -> float:
    """
    How much of a cluster's severity counts in a decision, 0-1.

    The same contract as `independence.confidence`, deliberately: route scoring
    multiplies by this and does not care which kind of object it came from.

    Anything not live contributes nothing rather than quietly contributing fully --
    `expired` and `removed` are not served, and if one reaches a decision path the
    safe reading is zero.
    """
    if status == ClusterStatus.CORROBORATED:
        return CORROBORATED_WEIGHT
    if status == ClusterStatus.PROVISIONAL:
        return PROVISIONAL_WEIGHT
    return 0.0


def severity_for(reporter_count: int) -> float:
    """
    Severity at `observed_at`, 0-100, from the number of independent reporters.

    Linear in reporters and capped well below the event flags:

        2 -> 40    3 -> 50    4 -> 55    5+ -> 55 (capped)

    Two properties are load-bearing. **The cap** keeps a cluster from ever
    outranking a live event: at 55 × 0.6 a cluster contributes at most 33 against a
    fire's 70, so a road on fire always wins the ranking, which is the correct
    ordering for a routing decision. **The flatness past four** is there because
    reporter count past a handful stops being evidence about the place and starts
    being evidence about how many people use the app on that street.

    It is deliberately not a function of the reports' categories. Weighting a
    violent family above a property one would be the product forming a view about
    how bad different crimes are, which is both outside what it can support and the
    judgement `framing.py` exists to keep it out of.
    """
    if reporter_count < MIN_REPORTERS_TO_PUBLISH:
        return 0.0
    return float(min(55.0, 20.0 + 10.0 * reporter_count))


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------


def independent_reporters(user_ids: Iterable[str]) -> set[str]:
    """
    The distinct accounts among these report authors.

    The counterpart of `independence.independent_publishers`, and routed through a
    function for the same reason: when there is something better than "distinct
    account" to say here — a verified phone, a device attestation, a reputation
    score — this is the one place that changes.

    Ten reports from one account collapse to one. That is the whole job.

    >>> sorted(independent_reporters(["a", "a", "b"]))
    ['a', 'b']
    """
    return {str(user_id) for user_id in user_ids}


def eligible_reporters(
    reports: Iterable[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """
    The reports that may count toward corroboration.

    Each mapping needs `user_id`, `incident_date_time`, `account_created_at` and
    `status`. Three gates, in the order they are cheapest to fail:

    1. `status == 'filed'` — a withdrawn report has been retracted by its author
       and a removed one has been taken down. Neither corroborates anything, and
       both rows stay, which is why this is a filter and not a delete.
    2. the account existed `MIN_ACCOUNT_AGE_HOURS` before the incident — the
       anti-sybil gate. See that constant for the cost it imposes on a real
       witness, which is real and accepted.
    3. one report per account — the first by incident time. A second report from
       the same person is kept in the cluster's `report_count` but adds nothing to
       `reporter_count`, exactly as a same-outlet follow-up does in Rumour Guard.

    Deliberately **not** here: a phone-verification gate and a proximity check.
    Both are named in the module docstring with the reason each is absent; this is
    the function they would go in.
    """
    filed = [report for report in reports if report.get("status") == "filed"]

    aged: list[Mapping[str, object]] = []
    for report in filed:
        incident = report.get("incident_date_time")
        created = report.get("account_created_at")
        if not isinstance(incident, datetime) or not isinstance(created, datetime):
            # No account age to check against means the gate cannot be applied,
            # and an unapplied gate must not pass silently.
            continue
        if incident - created >= timedelta(hours=MIN_ACCOUNT_AGE_HOURS):
            aged.append(report)

    first_by_account: dict[str, Mapping[str, object]] = {}
    for report in sorted(
        aged,
        key=lambda r: r["incident_date_time"],  # type: ignore[index,return-value]
    ):
        account = str(report.get("user_id"))
        first_by_account.setdefault(account, report)
    return list(first_by_account.values())


# ---------------------------------------------------------------------------
# The one sentence a cluster may say
# ---------------------------------------------------------------------------

MAX_SPAN_DAYS_PHRASE: Final[int] = 60
"""
Past this the phrase would be stating a span longer than any cluster can live, so
it is clamped. A defensive bound, not an expected one: `CLUSTER_WINDOW` is 14 days.
"""


def to_cluster_statement(*, reporter_count: int, radius_m: int, span: timedelta) -> str:
    """
    The only way to produce `community_clusters.statement`.

    The analogue of `framing.to_mobility_statement`, and the reason it exists is
    the same: the product's published claims come from a template that can be read
    in one place, not from a string built at a call site.

    What it may say is a **count and a recency**:

        "3 independent reports within 200 m in the last 6 days"

    What it may not say is anything about what happened. No category, no family, no
    severity word, no characterisation of the place or the people — which is why
    this takes a count and two numbers and has no access to a report's text at all.
    A function that cannot see the narrative cannot leak it.

    The output goes through `framing.assert_mobility_safe`, so there is one banned
    vocabulary for the whole product with two producers rather than two lists that
    drift. It also inherits that guard's length cap and its refusal of URLs.

    Raises `FramingViolation` if the result somehow fails the guard. That is not a
    reachable branch today — the template has no free text in it — and it is here
    because the day someone adds a place name to this sentence is the day it
    becomes reachable.
    """
    if reporter_count < MIN_REPORTERS_TO_PUBLISH:
        raise ValueError(
            f"a cluster statement needs at least {MIN_REPORTERS_TO_PUBLISH} reporters; "
            f"got {reporter_count}. Nothing below that is published at all -- see "
            "status_for()."
        )

    days = max(1, min(MAX_SPAN_DAYS_PHRASE, round(span.total_seconds() / 86_400)))
    day_phrase = "day" if days == 1 else "days"
    report_phrase = "report" if reporter_count == 1 else "reports"

    statement = (
        f"{reporter_count} independent {report_phrase} within {radius_m} m "
        f"in the last {days} {day_phrase}."
    )
    assert_mobility_safe(statement)
    return statement
