"""
Whether to interrupt someone. B6a / S16, and the whole of the alert-fatigue risk.

The concept document names alert fatigue as a top risk (§12) and
`IMPLEMENTATION_PLAN.md` S16 asks for *"conservative thresholds and a documented
rate cap per user per hour, from day one, with a test"*. This module is the
"from day one" part: every reason an alert is or is not sent lives here, as one
pure function over plain data.

## Why this is pure

`decide()` takes no session, touches no clock and performs no I/O. It is handed
the flag, the preferences, the ledger counts and the instant. That is not
fastidiousness — it is the only way the rate cap gets a test that means anything.
A cap implemented inside the dispatcher's loop, mixed in with database calls and
an HTTP client, can only be tested by standing up Postgres and Expo, which means
in practice it is tested once by hand and then trusted forever.

Here, `tests/invariants/test_alert_fatigue.py` can assert the fourth alert in an
hour is refused, in microseconds, with no fixtures.

## The decision, in the order the gates actually fire

    already_sent        this user has been told about this flag before
    category_muted      they turned this category off
    below_min_severity  not bad enough to be worth a buzz
    quiet_hours         they are asleep
    rate_capped         they have had enough already this hour
    allowed             send it

Order is deliberate and is itself a policy statement. The cheap, user-expressed
reasons come first, so that an alert refused because the user muted the category
does **not** consume one of their three hourly slots. Putting `rate_capped` first
would let a stream of muted chronic flags exhaust the cap and silence the one
corridor alert that mattered.

`already_sent` is first because it is the only gate that is about correctness
rather than preference: re-sending is a bug in the sweep, not a choice.

## Chronic alerts are off by default, and that is the only lever

A chronic flag is D02's police-statistics baseline — a historical average with a
2 km radius, which never moves and never expires. Pushing a notification about
one means telling somebody "this area has a history" every time they leave the
house. That is the "stale red zones" product demo beat 5 exists to disclaim, and
concept document §9 commits to not labelling areas permanently.

So `chronic_alerts` defaults to false and there is no second, hidden gate. An
earlier draft of this module had one — a `CHRONIC_REQUIRES_OPT_IN` refusal
sitting after the category check — and it was dead code: the category check
*is* the opt-in, so a user who had turned the switch on passed both and a user
who had not was already refused. A switch the product offers and then silently
ignores is worse than no switch.

What makes opting in survivable is the `already_sent` gate above: one alert per
flag, ever. Without it a chronic flag, which never expires, would re-qualify on
every sweep forever. It is still worth being plain about the cost, and the
preferences screen says so when the switch is flipped — Dhaka has dozens of
chronic flags, each good for one alert, and they share the same hourly budget as
the corridor alerts that are actually urgent.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from app.contracts.risk import IncidentKind, RiskFlag
from app.scoring.decay import DHAKA_TZ, effective_severity

__all__ = [
    "DEFAULT_PREFERENCES",
    "RATE_WINDOW",
    "AlertCategory",
    "AlertDecision",
    "AlertPlan",
    "AlertPreferences",
    "Refusal",
    "category_for",
    "decide",
    "dhaka_hour",
    "in_quiet_hours",
    "plan_for_device",
]

RATE_WINDOW: Final = timedelta(hours=1)
"""
The window the per-user cap is measured over.

An hour rather than a day because fatigue is a burst phenomenon: six alerts
spread across a day is tolerable and six in ten minutes is why people turn
notifications off. A daily cap would permit exactly the burst it should prevent.
"""


class AlertCategory(StrEnum):
    """
    What kind of interruption this is. The unit of user preference.

    Three, not one per `IncidentKind`. The categories are cut by *what the user
    would decide differently about*, which is a product question, and nobody has
    an opinion about waterlogging separately from construction. They do have an
    opinion about "something now" versus "something later" versus "somewhere has
    a history".

    `TEST` is not a user preference: it is what `POST /notifications/test`
    records in the ledger, so a walkthrough send is visible in the history and
    counts against the cap like anything else.
    """

    CORRIDOR = "corridor"
    SCHEDULED = "scheduled"
    CHRONIC = "chronic"
    TEST = "test"


class Refusal(StrEnum):
    """
    Why an alert was not sent.

    A closed set rather than a free-text reason, because these are counted: the
    dispatcher reports them as `AgentResult.metrics`, so a rehearsal can see that
    nothing was sent because everything was below `min_severity` rather than
    because the pipeline is broken. That distinction is invisible when the only
    observable is "0 sent".
    """

    ALREADY_SENT = "already_sent"
    CATEGORY_MUTED = "category_muted"
    BELOW_MIN_SEVERITY = "below_min_severity"
    QUIET_HOURS = "quiet_hours"
    RATE_CAPPED = "rate_capped"


@dataclass(frozen=True, slots=True)
class AlertPreferences:
    """
    One user's answer to "what may interrupt me".

    Mirrors `public.notification_preferences`, and the defaults here must mirror
    that table's column defaults — `test_defaults_match_the_migration` asserts
    they do by reading the SQL, because two sources of truth for a default is how
    a user who never opened the screen ends up on different rules from one who
    opened it and changed nothing.
    """

    corridor_alerts: bool = True
    scheduled_alerts: bool = True
    chronic_alerts: bool = False
    min_severity: float = 40.0
    quiet_hours_start: int | None = None
    quiet_hours_end: int | None = None
    max_per_hour: int | None = None

    def allows(self, category: AlertCategory) -> bool:
        match category:
            case AlertCategory.CORRIDOR:
                return self.corridor_alerts
            case AlertCategory.SCHEDULED:
                return self.scheduled_alerts
            case AlertCategory.CHRONIC:
                return self.chronic_alerts
            case AlertCategory.TEST:
                # A test send is explicitly requested by the user, in the app,
                # seconds earlier. Gating it on a preference would make the
                # walkthrough's "nothing arrived" ambiguous between "push is
                # broken" and "you have corridor alerts off".
                return True

    def effective_cap(self, system_cap: int) -> int:
        """
        The cap that applies: the stricter of the user's and the system's.

        A user may make themselves quieter, never louder. Taking the `min` rather
        than trusting the column is what makes that true — otherwise a stale row
        from before the setting was lowered would override it, and a client bug
        writing `max_per_hour = 999` would disable the cap entirely.
        """
        if self.max_per_hour is None:
            return system_cap
        return min(system_cap, self.max_per_hour)


DEFAULT_PREFERENCES: Final = AlertPreferences()
"""What a user with no `notification_preferences` row gets."""


@dataclass(frozen=True, slots=True)
class AlertDecision:
    """
    The outcome. `send` is the only field a caller may branch on.

    `refusal` and `severity` are for the record: the dispatcher counts refusals
    into its metrics, and `severity` is written to `sent_alerts.severity_at_send`
    so the history can explain an alert whose flag has since decayed below the
    threshold that let it through.
    """

    send: bool
    category: AlertCategory
    severity: float
    refusal: Refusal | None = None

    @property
    def reason(self) -> str:
        return self.refusal.value if self.refusal else "allowed"


@dataclass(frozen=True, slots=True)
class AlertPlan:
    """
    What to send to one device this sweep, and why everything else was refused.

    `sends` is ordered worst-first and is already capped: the executor sends every
    entry without re-checking, because the cap arithmetic happened while the plan
    was built. `refusals` is a count per reason, which is what makes a quiet sweep
    distinguishable from a broken one in `AgentResult.metrics`.
    """

    sends: list[tuple[RiskFlag, AlertDecision]] = field(default_factory=list)
    refusals: Counter[str] = field(default_factory=Counter)


# ---------------------------------------------------------------------------
# Categorising a flag
# ---------------------------------------------------------------------------

def category_for(flag: RiskFlag, *, at: datetime) -> AlertCategory:
    """
    Which interruption category this flag belongs to.

    Scheduled beats chronic beats corridor, and the order is the point: a
    forward-dated flag is `SCHEDULED` whatever its kind, because what the user is
    deciding about is "later" versus "now", not the kind of event.

    A flag is scheduled when its window has not opened yet. `valid_from` in the
    past means the window is open and it is simply happening — D09's own
    `isScheduledFlag` on the client uses the same test, and
    `test_the_client_and_server_agree_on_scheduled` pins that they agree.
    """
    if flag.valid_from is not None and flag.valid_from > at:
        return AlertCategory.SCHEDULED
    if flag.kind == IncidentKind.CHRONIC:
        return AlertCategory.CHRONIC
    return AlertCategory.CORRIDOR


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------

def dhaka_hour(at: datetime) -> int:
    """
    The Dhaka-local hour of `at`, 0-23.

    Quiet hours are a claim about the user's night, and every instant in this
    system is UTC by the time it gets here. A naive datetime is read as UTC, the
    same convention `decay.hour_multiplier` uses — treating it as local would
    shift every boundary by six hours, which for a 22:00 start means alerting
    people at 4 a.m.

    `DHAKA_TZ` is imported from `scoring.decay` rather than redefined, and it is a
    fixed +06:00 offset rather than a `ZoneInfo` lookup. Both details matter.
    Bangladesh has observed no DST since 2010, so the offset is exact; and
    `ZoneInfo("Asia/Dhaka")` raises `ZoneInfoNotFoundError` on a stock Windows
    Python, which is what the developers on this project run. A second definition
    of the same timezone is also how the decay curve and the quiet hours end up
    disagreeing about when the night starts.
    """
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(DHAKA_TZ).hour


def in_quiet_hours(hour: int, start: int | None, end: int | None) -> bool:
    """
    Whether `hour` falls in [start, end), with wrapping.

    Wrapping is the normal case, not the edge case: quiet hours are a night, so
    22 -> 7 is what a user will actually enter, and a naive `start <= h < end`
    returns False for every hour of it. `start == end` is treated as empty rather
    than as "all day": a user who sets both to 8 has expressed nothing, and
    silencing them permanently would be the worst available reading.
    """
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

def decide(
    *,
    flag: RiskFlag,
    prefs: AlertPreferences,
    already_alerted_flag_ids: frozenset[UUID],
    sent_in_window: int,
    system_cap: int,
    at: datetime,
) -> AlertDecision:
    """
    Whether to send `flag` to a user with these preferences, right now.

    Arguments, and why each is passed rather than fetched:

    * `already_alerted_flag_ids` — the flags this user has ever been alerted
      about. Passed as a set so the dispatcher reads the ledger once per user
      instead of once per flag; a sweep over 60 flags and 50 devices would
      otherwise be 3000 queries a minute.
    * `sent_in_window` — how many alerts this user has had inside
      `RATE_WINDOW`. A count, not a list, because that is all the cap needs.
    * `system_cap` — `settings.MAX_ALERTS_PER_USER_PER_HOUR`. Injected so the
      test does not have to mutate global settings to check the boundary.
    * `at` — the instant. Never the wall clock; see the module docstring.

    `severity` on the result is `effective_severity`, not `severity_now`: an
    unconfirmed flag is published at reduced weight (S15 / `independence.py`),
    and the weight has to apply to the decision to interrupt as well as to route
    scoring. Interrupting someone at full severity for a single-source report
    would make "published at reduced weight" a claim about the map only.
    """
    category = category_for(flag, at=at)
    severity = effective_severity(severity_now=flag.severity_now, confidence=flag.confidence)

    def refuse(refusal: Refusal) -> AlertDecision:
        return AlertDecision(
            send=False, category=category, severity=severity, refusal=refusal
        )

    # 1. Correctness, not preference: the sweep must never re-interrupt.
    if flag.flag_id in already_alerted_flag_ids:
        return refuse(Refusal.ALREADY_SENT)

    # 2. The user turned this category off. For CHRONIC this *is* the opt-in —
    #    there is deliberately no second gate; see the module docstring.
    if not prefs.allows(category):
        return refuse(Refusal.CATEGORY_MUTED)

    # 3. Not bad enough to be worth the interruption.
    if severity < prefs.min_severity:
        return refuse(Refusal.BELOW_MIN_SEVERITY)

    # 4. Asleep. Checked before the cap, so a night-time alert that was
    #    suppressed does not spend a slot the morning might need.
    if in_quiet_hours(dhaka_hour(at), prefs.quiet_hours_start, prefs.quiet_hours_end):
        return refuse(Refusal.QUIET_HOURS)

    # 5. Enough for one hour. Last, so it only ever counts alerts that were
    #    genuinely worth sending.
    if sent_in_window >= prefs.effective_cap(system_cap):
        return refuse(Refusal.RATE_CAPPED)

    return AlertDecision(send=True, category=category, severity=severity)


def plan_for_device(
    *,
    flags: Sequence[RiskFlag],
    prefs: AlertPreferences,
    already_alerted_flag_ids: frozenset[UUID],
    sent_in_window: int,
    system_cap: int,
    at: datetime,
) -> AlertPlan:
    """
    Every decision for one device, in order, with the cap applied **within** the batch.

    This is the part of dispatch that cannot be got right by calling `decide()` in
    a loop, and it is worth its own function because the mistake is invisible.

    The bug it exists to prevent: a device sitting beside six qualifying flags,
    with `decide()` called once per flag and each call passed the same pre-sweep
    `sent_in_window`. Every one of the six passes the cap check — against a count
    that nothing has incremented — and the user gets six notifications from a
    system whose cap is three. The sweep's logs show six decisions, all of them
    correct in isolation. That was the first version of this loop.

    So the count is carried forward as the batch is walked, and the same goes for
    `already`: two flags cannot both be "the first alert about this flag".

    ## Why flags are reordered

    Worst first, by `severity_now`. `flags_near` returns them nearest-first, which
    is the wrong priority for an interruption — a minor obstruction 50 m away
    should not spend the user's last slot while a blocked road 400 m away is
    refused as `rate_capped`. When the cap bites, it has to bite the least
    important thing in the batch.

    Sorted on `severity_now` rather than on the confidence-damped `effective_severity`
    the decision uses. Deliberate: the ordering question is "which event is worse",
    and damping is about how sure we are. An unconfirmed report of a blocked road
    should still be *considered* before a confirmed minor delay — whether it clears
    the floor is then `decide()`'s business, not the sort's.
    """
    sends: list[tuple[RiskFlag, AlertDecision]] = []
    refusals: Counter[str] = Counter()
    seen = set(already_alerted_flag_ids)
    spent = sent_in_window

    for flag in sorted(flags, key=lambda candidate: candidate.severity_now, reverse=True):
        verdict = decide(
            flag=flag,
            prefs=prefs,
            already_alerted_flag_ids=frozenset(seen),
            sent_in_window=spent,
            system_cap=system_cap,
            at=at,
        )
        if not verdict.send:
            refusals[verdict.reason] += 1
            continue
        sends.append((flag, verdict))
        seen.add(flag.flag_id)
        spent += 1

    return AlertPlan(sends=sends, refusals=refusals)
