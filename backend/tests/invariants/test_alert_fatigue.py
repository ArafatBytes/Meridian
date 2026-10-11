"""
Invariant: **we do not become the thing people mute.**

Concept document §12 names alert fatigue as a top risk and
`IMPLEMENTATION_PLAN.md` S16 asks for *"conservative thresholds and a documented
rate cap per user per hour, from day one, with a test"*. This is that test, and
it is in `invariants/` rather than beside the module because the cap is a
commitment to the user, not an implementation detail: it is the reason it is safe
to leave notifications on.

Phase 3's exit criteria list "alert rate cap verified by test" as a line of its
own. `test_the_fourth_alert_in_an_hour_is_refused` is the line.

## What makes these tests worth having

Every one of these failures produces a *plausible* system. An uncapped
dispatcher works perfectly in a quiet hour and buries the user the first time
Dhaka has a bad afternoon — which is precisely the afternoon the product needed
to be trusted. A gate ordering that spends the cap on muted categories looks
identical in every log. None of it shows up in a device walkthrough, because a
walkthrough is one person for ten minutes.

They run in milliseconds and touch no database, which is the whole reason
`policy.decide` takes its ledger state as arguments rather than fetching it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.alerts.policy import (
    DEFAULT_PREFERENCES,
    RATE_WINDOW,
    AlertCategory,
    AlertPreferences,
    Refusal,
    category_for,
    decide,
    dhaka_hour,
    in_quiet_hours,
    plan_for_device,
)
from app.contracts.risk import IncidentKind, RiskFlag

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
MIGRATION = (
    BACKEND / "migrations" / "versions" / "20261010180000__push_devices_and_alerts.sql"
)

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)  # 15:00 in Dhaka — not quiet hours
SYSTEM_CAP = 3


def flag(
    *,
    severity_now: float = 60.0,
    status: str = "confirmed",
    confidence: float = 1.0,
    kind: IncidentKind = IncidentKind.FIRE,
    source_count: int = 3,
    valid_from: datetime | None = None,
    statement: str = "Road blocked near Bangshal.",
) -> RiskFlag:
    """A `RiskFlag` carrying only what the alert policy reads."""
    return RiskFlag(
        flag_id=uuid4(),
        event_key="test",
        kind=kind,
        status=status,  # type: ignore[arg-type]
        lat=23.75,
        lon=90.40,
        radius_m=400,
        severity_0=severity_now,
        severity_now=severity_now,
        half_life_hours=3.0,
        observed_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=6),
        source_count=source_count,
        sources=[],
        mobility_statement=statement,
        confidence=confidence,
        valid_from=valid_from,
    )


def verdict(
    candidate: RiskFlag | None = None,
    *,
    prefs: AlertPreferences | None = None,
    already: frozenset[UUID] = frozenset(),
    sent_in_window: int = 0,
    at: datetime = NOW,
):
    return decide(
        flag=candidate if candidate is not None else flag(),
        prefs=prefs if prefs is not None else AlertPreferences(),
        already_alerted_flag_ids=already,
        sent_in_window=sent_in_window,
        system_cap=SYSTEM_CAP,
        at=at,
    )


# ---------------------------------------------------------------------------
# 1. The rate cap. The line Phase 3 asks for.
# ---------------------------------------------------------------------------


def test_an_alert_is_sent_when_nothing_stands_in_the_way() -> None:
    """
    The control. A cap test that never sends anything would also pass with
    `decide` hard-wired to refuse, and then the whole file would be worthless.
    """
    result = verdict()
    assert result.send is True
    assert result.refusal is None
    assert result.reason == "allowed"


@pytest.mark.parametrize("already_sent", [0, 1, 2])
def test_alerts_up_to_the_cap_are_sent(already_sent: int) -> None:
    assert verdict(sent_in_window=already_sent).send is True


def test_the_fourth_alert_in_an_hour_is_refused() -> None:
    """
    `MAX_ALERTS_PER_USER_PER_HOUR` is 3, so the fourth is refused.

    The boundary is `>=`, not `>`: with three already sent the user has had their
    allowance, and an off-by-one here means four. Asserting the refusal *reason*
    as well as the refusal matters — a flag refused for being below the severity
    floor would satisfy a bare `send is False` and tell us nothing about the cap.
    """
    result = verdict(sent_in_window=SYSTEM_CAP)
    assert result.send is False
    assert result.refusal is Refusal.RATE_CAPPED


def test_a_user_may_be_quieter_than_the_system_but_never_louder() -> None:
    """
    `effective_cap` takes the min of the two.

    The second half is the one that matters: a client bug, or a hand-edited row,
    writing `max_per_hour = 999` must not be able to switch the cap off. The cap
    exists to protect the user from us, so it cannot be ours to raise.
    """
    strict = AlertPreferences(max_per_hour=1)
    assert verdict(prefs=strict, sent_in_window=0).send is True
    assert verdict(prefs=strict, sent_in_window=1).refusal is Refusal.RATE_CAPPED

    greedy = AlertPreferences(max_per_hour=999)
    assert greedy.effective_cap(SYSTEM_CAP) == SYSTEM_CAP
    assert verdict(prefs=greedy, sent_in_window=SYSTEM_CAP).refusal is Refusal.RATE_CAPPED


def test_the_rate_window_is_an_hour() -> None:
    """
    An hour, not a day.

    Fatigue is a burst phenomenon: six alerts across a day is tolerable, six in
    ten minutes is why people turn notifications off. A daily cap would permit
    exactly the burst it is supposed to prevent, and would pass every other test
    in this file.
    """
    assert RATE_WINDOW == timedelta(hours=1)


# ---------------------------------------------------------------------------
# 2. Gate order. The subtle one.
# ---------------------------------------------------------------------------


def test_a_refused_alert_does_not_consume_the_cap() -> None:
    """
    Cheap refusals come before the cap, so they cannot exhaust it.

    This is the failure that would never be noticed. If `rate_capped` were
    checked first, a user standing near a dozen muted chronic flags would have
    their three slots spent on alerts that were never going to be sent — and the
    one corridor alert that mattered would be refused as `rate_capped`. The
    system would look like it was working: three decisions made, cap respected,
    nothing delivered.

    Checked by asserting the *reason*, which is the only observable difference.
    """
    muted = AlertPreferences(corridor_alerts=False)
    result = verdict(prefs=muted, sent_in_window=SYSTEM_CAP)
    assert result.refusal is Refusal.CATEGORY_MUTED, (
        "a muted category must be refused for being muted, not for the cap — "
        "otherwise muted flags eat the user's hourly allowance"
    )

    quiet = AlertPreferences(quiet_hours_start=0, quiet_hours_end=23)
    assert verdict(prefs=quiet, sent_in_window=SYSTEM_CAP).refusal is Refusal.QUIET_HOURS

    low = AlertPreferences(min_severity=90)
    assert verdict(prefs=low, sent_in_window=SYSTEM_CAP).refusal is Refusal.BELOW_MIN_SEVERITY


def test_already_sent_beats_every_other_reason() -> None:
    """
    The debounce is first because it is about correctness, not preference.

    A flag the user has already been told about must be refused as `already_sent`
    whatever else is true, so that a sweep re-reading the same flag is
    distinguishable in the metrics from a sweep refusing new ones.
    """
    seen = flag()
    result = verdict(
        seen,
        prefs=AlertPreferences(corridor_alerts=False, min_severity=100),
        already=frozenset({seen.flag_id}),
        sent_in_window=SYSTEM_CAP,
    )
    assert result.refusal is Refusal.ALREADY_SENT


# ---------------------------------------------------------------------------
# 3. One alert per flag, ever
# ---------------------------------------------------------------------------


def test_the_same_flag_never_interrupts_twice() -> None:
    """
    S17's "no repeat for the same flag", at the policy layer.

    The database also enforces it with a unique constraint, and both are needed:
    this one stops the sweep deciding to send, and that one stops two workers
    deciding simultaneously. Neither is redundant.
    """
    once = flag()
    assert verdict(once).send is True
    assert verdict(once, already=frozenset({once.flag_id})).refusal is Refusal.ALREADY_SENT


def test_a_different_flag_at_the_same_place_is_still_new() -> None:
    """
    The debounce is on flag identity, not on location.

    Keying it on coordinates would be the tempting "smarter" version and would be
    wrong: a fire at a junction this morning and a blocked road at the same
    junction this afternoon are two things the user needs to know about. Dedup of
    *the same event* reported twice is Rumour Guard's job (D05), upstream of here,
    and it has already happened by the time a flag exists.
    """
    first = flag()
    second = flag()
    assert verdict(second, already=frozenset({first.flag_id})).send is True


# ---------------------------------------------------------------------------
# 4. Severity, with confidence applied
# ---------------------------------------------------------------------------


def test_the_severity_floor_uses_confidence_damped_severity() -> None:
    """
    An unconfirmed flag is judged at reduced weight, here as well as in routing.

    S15 commits to publishing unconfirmed flags *at reduced weight* rather than
    suppressing them. If the alert threshold compared raw `severity_now`, that
    commitment would apply to the map and to route scoring but not to the one
    place it is most consequential — interrupting somebody on the strength of a
    single uncorroborated report.

    55 raw at 0.6 confidence is 33, which is below the default floor of 40. The
    same flag confirmed is 55 and clears it. Nothing about the event changed; only
    how much we are willing to stake on it.
    """
    unconfirmed = flag(severity_now=55.0, status="unconfirmed", confidence=0.6, source_count=1)
    result = verdict(unconfirmed)
    assert result.severity == pytest.approx(33.0)
    assert result.refusal is Refusal.BELOW_MIN_SEVERITY

    confirmed = flag(severity_now=55.0, status="confirmed", confidence=1.0)
    assert verdict(confirmed).send is True


def test_the_floor_is_inclusive_at_the_threshold() -> None:
    """Exactly at `min_severity` sends. A flag at the floor is on the allowed side."""
    assert verdict(flag(severity_now=40.0), prefs=AlertPreferences(min_severity=40)).send is True
    assert (
        verdict(flag(severity_now=39.9), prefs=AlertPreferences(min_severity=40)).refusal
        is Refusal.BELOW_MIN_SEVERITY
    )


# ---------------------------------------------------------------------------
# 5. Categories
# ---------------------------------------------------------------------------


def test_chronic_flags_do_not_interrupt_by_default() -> None:
    """
    The most important default in the feature.

    A chronic flag is D02's police-statistics baseline — a historical average with
    a 2 km radius, covering most of Dhaka, which never moves and never expires.
    Pushing one means telling somebody "this area has a history" every time they
    leave the house: useless, and exactly the "stale red zones" product demo beat
    5 exists to disclaim. Concept document §9 commits to not labelling areas
    permanently, and a recurring notification is the most permanent label there
    is.
    """
    chronic = flag(kind=IncidentKind.CHRONIC, severity_now=80.0)
    assert DEFAULT_PREFERENCES.chronic_alerts is False
    assert verdict(chronic).refusal is Refusal.CATEGORY_MUTED


def test_chronic_alerts_are_honoured_when_switched_on() -> None:
    """
    A switch the product offers must actually work.

    An earlier draft refused chronic alerts twice — once on the category check and
    again on a dedicated `CHRONIC_REQUIRES_OPT_IN` gate — which made the second
    gate dead code and the switch a lie. Pinned here so it cannot come back: the
    only lever is the preference.
    """
    chronic = flag(kind=IncidentKind.CHRONIC, severity_now=80.0)
    assert verdict(chronic, prefs=AlertPreferences(chronic_alerts=True)).send is True


def test_a_forward_dated_flag_is_scheduled_whatever_its_kind() -> None:
    """
    D09's windows get their own category, and it wins over kind.

    What the user is choosing between is "now" and "later", not between kinds of
    event — so a chronic flag with a future window is `SCHEDULED`. The ordering is
    asserted rather than assumed because `category_for` checks `valid_from` first
    and a reader would reasonably expect kind to dominate.
    """
    later = NOW + timedelta(hours=5)
    assert category_for(flag(valid_from=later), at=NOW) is AlertCategory.SCHEDULED
    assert (
        category_for(flag(kind=IncidentKind.CHRONIC, valid_from=later), at=NOW)
        is AlertCategory.SCHEDULED
    )


def test_a_window_that_has_opened_is_no_longer_scheduled() -> None:
    """
    `valid_from` in the past means it is simply happening.

    The same test the client's `isScheduledFlag` uses, so a flag does not read as
    "later today" on the lock screen while the map has already stopped marking it
    as scheduled.
    """
    assert category_for(flag(valid_from=NOW - timedelta(hours=1)), at=NOW) is AlertCategory.CORRIDOR
    assert category_for(flag(valid_from=None), at=NOW) is AlertCategory.CORRIDOR


def test_each_category_can_be_muted_independently() -> None:
    """Three categories, three switches, no cross-talk."""
    later = NOW + timedelta(hours=5)
    only_corridor = AlertPreferences(scheduled_alerts=False, chronic_alerts=False)
    assert verdict(flag(), prefs=only_corridor).send is True
    assert verdict(flag(valid_from=later), prefs=only_corridor).refusal is Refusal.CATEGORY_MUTED

    only_scheduled = AlertPreferences(corridor_alerts=False, scheduled_alerts=True)
    assert verdict(flag(valid_from=later), prefs=only_scheduled).send is True
    assert verdict(flag(), prefs=only_scheduled).refusal is Refusal.CATEGORY_MUTED


def test_a_test_alert_ignores_category_preferences() -> None:
    """
    A test send was explicitly asked for, seconds earlier, in the app.

    Gating it on a preference would make the walkthrough's "nothing arrived"
    ambiguous between "push is broken" and "you have corridor alerts off", which
    defeats the only purpose the endpoint has.
    """
    silent = AlertPreferences(
        corridor_alerts=False, scheduled_alerts=False, chronic_alerts=False
    )
    assert silent.allows(AlertCategory.TEST) is True


# ---------------------------------------------------------------------------
# 6. Quiet hours
# ---------------------------------------------------------------------------


def test_quiet_hours_wrap_around_midnight() -> None:
    """
    The normal case, not the edge case.

    Quiet hours are a night, so 22 -> 7 is what a user will actually enter, and a
    naive `start <= hour < end` returns False for every hour of it — silently
    alerting them all night. Wrapping is the default reading here.
    """
    for hour in (22, 23, 0, 3, 6):
        assert in_quiet_hours(hour, 22, 7) is True, hour
    for hour in (7, 12, 21):
        assert in_quiet_hours(hour, 22, 7) is False, hour


def test_quiet_hours_without_wrapping_still_work() -> None:
    assert in_quiet_hours(14, 13, 17) is True
    assert in_quiet_hours(17, 13, 17) is False  # end is exclusive
    assert in_quiet_hours(13, 13, 17) is True  # start is inclusive


def test_equal_quiet_hours_mean_nothing_rather_than_everything() -> None:
    """
    `start == end` is empty, not all day.

    A user who sets both to 8 has expressed nothing coherent. Reading it as
    "silent for 24 hours" would be the worst available interpretation: they would
    stop receiving safety alerts entirely and nothing on the screen would say
    why.
    """
    assert in_quiet_hours(8, 8, 8) is False
    assert in_quiet_hours(20, 8, 8) is False


def test_no_quiet_hours_means_no_quiet_hours() -> None:
    assert in_quiet_hours(3, None, None) is False
    assert DEFAULT_PREFERENCES.quiet_hours_start is None


def test_quiet_hours_are_measured_in_dhaka_not_utc() -> None:
    """
    Six hours of difference, which is the whole night.

    Every instant in this system is UTC by the time it reaches the policy. If the
    hour were taken from the UTC clock, a user whose quiet hours start at 22:00
    would be alerted until 04:00 local — and the bug would be invisible to anyone
    testing during the day.
    """
    # 20:00 UTC is 02:00 in Dhaka: inside a 22->7 night.
    deep_night = datetime(2026, 10, 10, 20, 0, tzinfo=UTC)
    assert dhaka_hour(deep_night) == 2
    night_owl = AlertPreferences(quiet_hours_start=22, quiet_hours_end=7)
    assert verdict(prefs=night_owl, at=deep_night).refusal is Refusal.QUIET_HOURS

    # 09:00 UTC is 15:00 in Dhaka: the middle of the afternoon.
    assert dhaka_hour(NOW) == 15
    assert verdict(prefs=night_owl, at=NOW).send is True


def test_a_naive_instant_is_read_as_utc() -> None:
    """
    The same convention `decay.hour_multiplier` uses.

    Treating a naive datetime as *local* would shift every boundary by six hours.
    Nothing in this system should produce a naive instant, which is exactly why
    the fallback has to be the harmless one rather than left to chance.
    """
    assert dhaka_hour(datetime(2026, 10, 10, 9, 0)) == dhaka_hour(NOW)


# ---------------------------------------------------------------------------
# 7. The defaults are the policy, so they are pinned to the migration
# ---------------------------------------------------------------------------


def test_defaults_match_the_migration() -> None:
    """
    `AlertPreferences`'s defaults and the table's column defaults must agree.

    Two sources of truth for a default is how a user who never opened the
    preferences screen ends up on different rules from one who opened it and
    changed nothing — and the difference would be invisible, because both paths
    produce a working alert.

    Read out of the SQL rather than duplicated here, so editing one side without
    the other fails this test by name.
    """
    sql = MIGRATION.read_text(encoding="utf-8")

    def column_default(column: str) -> str:
        # The type is `.+?` rather than `\S+` because `double precision` is two
        # words — the first version of this regex matched the three booleans and
        # silently skipped `min_severity`, which is the one with an argued value.
        match = re.search(rf"^\s*{column}\s+.+?\s+not null default (\S+?),?\s*$", sql, re.M)
        assert match, f"no default found for {column} in {MIGRATION.name}"
        return match.group(1)

    assert column_default("corridor_alerts") == "true"
    assert column_default("scheduled_alerts") == "true"
    assert column_default("chronic_alerts") == "false"
    assert float(column_default("min_severity")) == DEFAULT_PREFERENCES.min_severity

    assert DEFAULT_PREFERENCES.corridor_alerts is True
    assert DEFAULT_PREFERENCES.scheduled_alerts is True
    assert DEFAULT_PREFERENCES.chronic_alerts is False


def test_the_ledger_enforces_one_alert_per_user_per_flag() -> None:
    """
    The policy layer's debounce is backed by a database constraint.

    Asserted by reading the migration, which is crude and is also the only way to
    catch the failure that matters: the constraint being dropped during some
    later schema change, leaving the in-memory check as the only guard. Two
    workers racing would then both send.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "sent_alerts_one_per_user_per_flag" in sql
    assert re.search(r"unique\s*\(\s*user_id\s*,\s*flag_id\s*\)", sql), (
        "sent_alerts must carry UNIQUE (user_id, flag_id) — it is what makes the "
        "one-alert-per-flag debounce survive two workers sweeping at once"
    )

# ---------------------------------------------------------------------------
# 8. The cap across a whole batch. The bug that is invisible in a log.
# ---------------------------------------------------------------------------


def plan(
    flags: list[RiskFlag],
    *,
    prefs: AlertPreferences | None = None,
    already: frozenset[UUID] = frozenset(),
    sent_in_window: int = 0,
    at: datetime = NOW,
):
    return plan_for_device(
        flags=flags,
        prefs=prefs if prefs is not None else AlertPreferences(),
        already_alerted_flag_ids=already,
        sent_in_window=sent_in_window,
        system_cap=SYSTEM_CAP,
        at=at,
    )


def test_six_qualifying_flags_produce_three_alerts_not_six() -> None:
    """
    **The reason `plan_for_device` exists.**

    Call `decide()` once per flag in a loop and pass each call the same pre-sweep
    count, and all six pass the cap check — against a number nothing incremented.
    The user gets six notifications from a system whose cap is three, and every
    individual decision was correct. Nothing in the logs looks wrong.

    So the count is carried forward across the batch, and this is the test that
    says so. Six flags in, three sends out, three refused as `rate_capped`.
    """
    flags = [flag(severity_now=70.0 + index) for index in range(6)]
    result = plan(flags)
    assert len(result.sends) == SYSTEM_CAP, (
        f"{len(result.sends)} alerts planned for a cap of {SYSTEM_CAP} — the cap "
        "is not being carried across the batch"
    )
    assert result.refusals[Refusal.RATE_CAPPED.value] == 3


def test_the_batch_spends_its_slots_on_the_worst_flags() -> None:
    """
    When the cap bites it must bite the least important thing in the batch.

    `flags_near` returns nearest-first, which is the wrong priority for an
    interruption: a minor obstruction 50 m away should not spend the user's last
    slot while a blocked road 400 m away is refused. So the planner reorders by
    severity, and the three alerts that survive are the three worst.
    """
    severities = [20.0, 95.0, 55.0, 88.0, 41.0, 70.0]
    flags = [flag(severity_now=value) for value in severities]
    result = plan(flags)
    chosen = sorted(decision.severity for _, decision in result.sends)
    assert chosen == [70.0, 88.0, 95.0]


def test_a_user_at_their_cap_gets_nothing_from_a_fresh_batch() -> None:
    flags = [flag(severity_now=90.0) for _ in range(3)]
    result = plan(flags, sent_in_window=SYSTEM_CAP)
    assert result.sends == []
    assert result.refusals[Refusal.RATE_CAPPED.value] == 3


def test_one_flag_cannot_be_the_first_alert_twice() -> None:
    """
    `already` is carried forward inside the batch as well as the cap.

    The surface can legitimately return the same flag twice — two devices
    belonging to one user, overlapping radii — and without the running set both
    copies would pass the `already_sent` gate on the pre-sweep state.
    """
    duplicated = flag(severity_now=80.0)
    result = plan([duplicated, duplicated])
    assert len(result.sends) == 1
    assert result.refusals[Refusal.ALREADY_SENT.value] == 1


def test_refusals_are_counted_by_reason() -> None:
    """
    `AgentResult.metrics` is the only window into a quiet sweep.

    "0 sent" is ambiguous between a broken pipeline and a quiet city.
    `{"below_min_severity": 4}` tells them apart, so the counts have to be real.
    """
    result = plan(
        [
            flag(severity_now=10.0),  # below the floor
            flag(severity_now=12.0),  # below the floor
            flag(kind=IncidentKind.CHRONIC, severity_now=90.0),  # muted category
            flag(severity_now=80.0),  # sent
        ]
    )
    assert len(result.sends) == 1
    assert result.refusals[Refusal.BELOW_MIN_SEVERITY.value] == 2
    assert result.refusals[Refusal.CATEGORY_MUTED.value] == 1


def test_an_empty_batch_is_not_an_error() -> None:
    """The common case: a quiet minute. No flags, no sends, no refusals."""
    result = plan([])
    assert result.sends == []
    assert sum(result.refusals.values()) == 0
