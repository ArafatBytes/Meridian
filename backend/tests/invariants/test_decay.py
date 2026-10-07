"""
The decay engine, exhaustively. IMPLEMENTATION_PLAN.md S19: "pure, total,
exhaustively unit-tested, boundaries included".

These are unit tests of arithmetic, not invariants in the §4 sense, but they live in
`tests/invariants/` with the others because the thing they protect is one:
**every flag decays.** A decay function that quietly returned `severity_0` would pass
every other test in this suite and break the product's central ethical claim.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.risk import IncidentKind, TimeProfile
from app.scoring.decay import (
    DHAKA_TZ,
    SERVE_THRESHOLD,
    decay_anchor,
    elapsed_hours,
    expires_at_for,
    hour_multiplier,
    is_live,
    profile_for,
    severity_at,
    undecayed_severity,
)

T0 = datetime(2026, 10, 9, 6, 0, tzinfo=UTC)  # noon in Dhaka, a neutral-ish hour


# ---------------------------------------------------------------------------
# Halving
# ---------------------------------------------------------------------------


def test_severity_is_unchanged_at_the_observation_instant() -> None:
    assert undecayed_severity(
        severity_0=80.0, half_life_hours=3.0, observed_at=T0, at=T0
    ) == pytest.approx(80.0)


@pytest.mark.parametrize("half_lives", [1, 2, 3, 4, 10])
def test_severity_halves_once_per_half_life(half_lives: int) -> None:
    """The definition of a half-life, checked at several multiples rather than one."""
    half_life = 2.5
    got = undecayed_severity(
        severity_0=100.0,
        half_life_hours=half_life,
        observed_at=T0,
        at=T0 + timedelta(hours=half_life * half_lives),
    )
    assert got == pytest.approx(100.0 / 2**half_lives)


def test_severity_is_monotonically_non_increasing() -> None:
    """
    Walked hour by hour over four days.

    A test at two instants would pass for a function with a bug that made severity
    rise somewhere in the middle — and a flag that got *worse* with age is the one
    behaviour that would be read as fabrication rather than as a bug.
    """
    previous = float("inf")
    for hour in range(0, 96):
        current = undecayed_severity(
            severity_0=90.0,
            half_life_hours=6.0,
            observed_at=T0,
            at=T0 + timedelta(hours=hour),
        )
        assert current <= previous
        previous = current


def test_severity_approaches_but_never_reaches_zero() -> None:
    """Exponential decay has no zero. A flag is retired by expiry, not by arithmetic."""
    far = undecayed_severity(
        severity_0=100.0, half_life_hours=1.0, observed_at=T0, at=T0 + timedelta(days=30)
    )
    assert 0.0 < far < 1e-100


def test_zero_severity_stays_zero() -> None:
    assert undecayed_severity(
        severity_0=0.0, half_life_hours=3.0, observed_at=T0, at=T0 + timedelta(hours=9)
    ) == pytest.approx(0.0)


@pytest.mark.parametrize("half_life", [0.0, -1.0, -0.0001])
def test_a_non_positive_half_life_is_refused(half_life: float) -> None:
    """
    The same rule as the `risk_flags_half_life_positive` CHECK.

    Mandatory decay is §4's invariant; a half-life of zero or less is the shape a
    permanent area label would arrive in.
    """
    with pytest.raises(ValueError, match="half_life_hours must be positive"):
        undecayed_severity(
            severity_0=50.0, half_life_hours=half_life, observed_at=T0, at=T0
        )
    with pytest.raises(ValueError, match="half_life_hours must be positive"):
        expires_at_for(severity_0=50.0, half_life_hours=half_life, observed_at=T0)


# ---------------------------------------------------------------------------
# The anchor, and forward-dated flags
# ---------------------------------------------------------------------------


def test_anchor_is_observed_at_for_an_ordinary_flag() -> None:
    assert decay_anchor(T0, None) == T0


def test_anchor_is_valid_from_for_a_forward_dated_flag() -> None:
    """
    D09's reason for existing.

    A procession announced on Tuesday for Friday must not arrive already decayed by
    three days, which is what anchoring on `observed_at` would do.
    """
    window_opens = T0 + timedelta(days=3)
    assert decay_anchor(T0, window_opens) == window_opens


def test_a_flag_before_its_window_reads_at_full_severity() -> None:
    window_opens = T0 + timedelta(days=2)
    assert undecayed_severity(
        severity_0=60.0,
        half_life_hours=4.0,
        observed_at=T0,
        at=T0,
        valid_from=window_opens,
    ) == pytest.approx(60.0)


def test_elapsed_hours_never_goes_negative() -> None:
    assert elapsed_hours(T0, T0 - timedelta(hours=5)) == 0.0


def test_naive_instants_are_read_as_utc() -> None:
    """
    Not rejected, because the endpoint accepts a naive `as_of` and reads it as UTC.

    If this module disagreed with the endpoint, a client that omitted the `Z` would get
    a severity computed six hours out while the response still looked plausible.
    """
    naive = T0.replace(tzinfo=None)
    assert elapsed_hours(naive, T0 + timedelta(hours=2)) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Time-of-day modulation
# ---------------------------------------------------------------------------


def test_every_kind_has_a_24_entry_profile() -> None:
    for kind in IncidentKind:
        assert len(profile_for(kind).multipliers) == 24


def test_no_profile_means_no_modulation() -> None:
    assert hour_multiplier(None, T0) == 1.0


def test_the_multiplier_is_keyed_on_the_dhaka_hour_not_utc() -> None:
    """
    The six-hour trap, pinned.

    `T0` is 06:00 UTC, which is noon in Dhaka. A profile that is 1.0 everywhere except
    noon must fire at `T0`. If this module ever read the UTC hour instead, it would
    pick index 6 and this test is the only thing that notices.
    """
    noon_only = TimeProfile(multipliers=[1.0] * 12 + [2.0] + [1.0] * 11)
    assert T0.astimezone(DHAKA_TZ).hour == 12
    assert hour_multiplier(noon_only, T0) == 2.0


def test_the_traffic_profile_peaks_in_rush_hour_and_troughs_overnight() -> None:
    """The shape the rationale in `decay.py` claims, asserted rather than described."""
    multipliers = profile_for(IncidentKind.ROAD_ACCIDENT).multipliers
    assert multipliers[8] > multipliers[3]  # morning peak over the small hours
    assert multipliers[17] > multipliers[13]  # evening peak over the afternoon lull
    assert max(multipliers[16:20]) >= max(multipliers[7:10])  # evening is no milder


def test_the_chronic_profile_is_the_inverse_of_the_traffic_profile() -> None:
    chronic = profile_for(IncidentKind.CHRONIC).multipliers
    traffic = profile_for(IncidentKind.ROAD_ACCIDENT).multipliers
    assert chronic[2] > chronic[9]
    assert traffic[9] > traffic[2]


def test_severity_now_is_clamped_to_the_contract_range() -> None:
    """
    `RiskFlag.severity_now` is `ge=0, le=100`.

    A severity of 98 with a 1.25 multiplier is 122.5, and an unclamped value would make
    pydantic reject the whole response — a blank map rather than a bright pin.
    """
    boosted = TimeProfile(multipliers=[1.25] * 24)
    got = severity_at(
        severity_0=98.0,
        half_life_hours=100.0,
        observed_at=T0,
        at=T0,
        kind=IncidentKind.FIRE,
        time_profile=boosted,
    )
    assert got == 100.0


def test_a_flag_carried_profile_overrides_the_kind_default() -> None:
    flat_half = TimeProfile(multipliers=[0.5] * 24)
    got = severity_at(
        severity_0=40.0,
        half_life_hours=100.0,
        observed_at=T0,
        at=T0,
        kind=IncidentKind.ROAD_ACCIDENT,
        time_profile=flat_half,
    )
    assert got == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Expiry — the mirror of the SQL trigger
# ---------------------------------------------------------------------------


def test_expiry_is_exactly_where_severity_crosses_the_threshold() -> None:
    """
    The equivalence both surfaces rely on.

    `expires_at` is solved from the un-modulated curve, so at that instant the
    un-modulated severity is the serve threshold and not a hair more. This is what makes
    "still served" and "still above threshold" the same statement, which is why the
    endpoint can filter on a stored column and still be honest about severity.
    """
    expires = expires_at_for(severity_0=80.0, half_life_hours=3.0, observed_at=T0)
    at_expiry = undecayed_severity(
        severity_0=80.0, half_life_hours=3.0, observed_at=T0, at=expires
    )
    assert at_expiry == pytest.approx(SERVE_THRESHOLD)


@pytest.mark.parametrize(
    ("severity_0", "half_life_hours", "expected_hours"),
    [
        # t = H · log2(severity_0 / 5). Hand-computed from the trigger's arithmetic in
        # migration 20261007120000__risk_flags, which is the authority for this column.
        (10.0, 1.0, 1.0),  # log2(2)  = 1
        (20.0, 1.0, 2.0),  # log2(4)  = 2
        (40.0, 1.0, 3.0),  # log2(8)  = 3
        (80.0, 1.0, 4.0),  # log2(16) = 4
        (80.0, 3.5, 14.0),  # the fire default: 4 half-lives of 3.5h
        (5.0, 6.0, 0.0),  # already at the threshold: expires immediately
        (1.0, 6.0, 0.0),  # born below it: max(severity_0, threshold) keeps log defined
    ],
)
def test_expiry_matches_the_sql_trigger_arithmetic(
    severity_0: float, half_life_hours: float, expected_hours: float
) -> None:
    """
    `expires_at_for()` must return what `public.risk_flags_set_expires_at()` would.

    This is the test `app/scoring/decay.py` names as the thing that pins the one formula
    that genuinely exists in two languages. The expected values are computed by hand from
    the trigger rather than from the Python, so the test cannot agree with a change to
    both sides at once.
    """
    got = expires_at_for(
        severity_0=severity_0, half_life_hours=half_life_hours, observed_at=T0
    )
    assert got == T0 + timedelta(hours=expected_hours)


def test_valid_to_extends_expiry_past_the_decay_curve() -> None:
    """
    `greatest(decay-derived, valid_to)` in the trigger.

    A procession announced today for tomorrow evening must not expire tonight.
    """
    window_closes = T0 + timedelta(days=2)
    got = expires_at_for(
        severity_0=50.0, half_life_hours=1.0, observed_at=T0, valid_to=window_closes
    )
    assert got == window_closes


def test_valid_to_does_not_shorten_expiry() -> None:
    """`greatest`, not `coalesce`. A short window must not retire a long-lived flag."""
    decay_only = expires_at_for(severity_0=90.0, half_life_hours=100.0, observed_at=T0)
    with_window = expires_at_for(
        severity_0=90.0,
        half_life_hours=100.0,
        observed_at=T0,
        valid_to=T0 + timedelta(hours=1),
    )
    assert with_window == decay_only


# ---------------------------------------------------------------------------
# is_live — the Python statement of `_LIVE_PREDICATE`
# ---------------------------------------------------------------------------


def test_a_flag_is_live_up_to_but_not_at_its_expiry() -> None:
    expires = T0 + timedelta(hours=4)
    assert is_live(at=expires - timedelta(seconds=1), expires_at=expires)
    assert not is_live(at=expires, expires_at=expires)
    assert not is_live(at=expires + timedelta(seconds=1), expires_at=expires)


def test_a_closed_window_retires_a_flag_inside_a_live_decay_curve() -> None:
    """
    The reason `valid_to` is tested separately from `expires_at`.

    The trigger takes the later of the two, so a flag whose window closed at noon can
    still sit well inside its decay curve — and a procession that finished at noon has
    no business on the map at midnight.
    """
    closed = T0 + timedelta(hours=2)
    later = T0 + timedelta(hours=10)
    assert not is_live(at=T0 + timedelta(hours=5), expires_at=later, valid_to=closed)
