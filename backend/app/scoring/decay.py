"""
The decay engine — severity as a function of time. IMPLEMENTATION_PLAN.md S19.

    severity(t) = severity_0 · 0.5^(elapsed / half_life) · time_profile[hour]

Pure functions over explicit instants. Nothing here reads the wall clock, because
D02's "as of" control, D09's forward-looking view and the test suite all depend on
the caller choosing the moment.

Computed on read, never stored
-----------------------------
A cron job that rewrites every row's severity on a timer is the obvious
implementation and it is worse in every way that matters here: it can fall behind,
it cannot answer "what will this look like in six hours", and the number it writes
is stale the instant after it writes it. `risk_flags.severity_0` is the severity at
`observed_at` and never changes; what a client is served is this function's output.

Two numbers live in two places, deliberately
--------------------------------------------
`SERVE_THRESHOLD` and the halving formula also exist in SQL, in
`public.risk_flags_set_expires_at()` (migration `20261007120000__risk_flags`),
which derives `expires_at`. That duplication is not an accident and it is not
avoidable:

* the database has to own `expires_at`, because it is a stored column that must be
  correct no matter who inserts the row;
* Python has to own severity-now, because the seeded surface has no database at
  all and the whole offline demo path runs through it.

So the rule is one formula in two implementations that are checked against each
other, rather than one implementation and a surface that cannot work offline.
`tests/invariants/test_decay_agrees_with_sql_expiry.py` pins the agreement:
`expires_at_for()` here must return what the trigger would. **If you change either
one, change both, and that test will tell you if you did not.**

The time-of-day profile is excluded from the expiry decision
------------------------------------------------------------
`severity_at()` applies the hour multiplier; `expires_at_for()` does not. A flag is
retired when the *event* has faded, and an event does not end because it is 4 a.m.
The multiplier says how much a live condition matters right now; it is not a claim
about whether the condition exists. Keeping it out of expiry is also what preserves
the equivalence the surfaces rely on: without it, un-modulated severity falls below
`SERVE_THRESHOLD` at exactly `expires_at`, so "still served" and "still above
threshold" are the same statement.
"""

import math
from datetime import UTC, datetime, timedelta, timezone
from typing import Final

from app.contracts.risk import IncidentKind, TimeProfile

SERVE_THRESHOLD: Final[float] = 5.0
"""
Below this, on the 0-100 scale, a flag is not worth showing.

MIRRORS the `threshold` constant in `public.risk_flags_set_expires_at()`. See the
module docstring. Changing one without the other means flags that are served with
no severity, or flags with severity that are not served.
"""

DHAKA_TZ: Final[timezone] = timezone(timedelta(hours=6), "Asia/Dhaka")
"""
Hour-of-day means hour *in Dhaka*.

A fixed +06:00 offset rather than a `zoneinfo` lookup: Bangladesh has had no DST
since 2009, so the offset is a constant, and depending on `zoneinfo` would mean
depending on the host having a tz database — which Windows does not ship, and this
project is developed on Windows.

Getting this wrong is a silent six-hour error: flags stored in UTC would get the
morning peak applied at 2 p.m. local, and the result still looks like a plausible
curve.
"""


# ---------------------------------------------------------------------------
# Time-of-day profiles
# ---------------------------------------------------------------------------
# 24 multipliers, index = hour in Dhaka local time, 1.0 = neutral.
#
# S19 says: derive these from the chronic corpus where the data supports it,
# hand-set them with a written rationale where it does not, and **document which is
# which**. So, plainly: ALL FOUR PROFILES BELOW ARE HAND-SET. The chronic corpus is
# B11; `scripts/crime_risk_model.json` is police-unit totals with no hour column, so
# there is nothing here to derive from yet. Each rationale is a stated belief about
# Dhaka traffic, and each is falsifiable once the corpus exists.
#
# They are kept mild on purpose — 0.70 to 1.25 rather than 0.3 to 2.0. A multiplier
# strong enough to retire a flag overnight and resurrect it at breakfast would make
# the surface look unstable, and the honest claim is "this matters somewhat more in
# rush hour", not "this triples".

_FLAT: Final[list[float]] = [1.0] * 24

_TRAFFIC_PEAKED: Final[list[float]] = [
    # 00    01    02    03    04    05
    0.75, 0.75, 0.75, 0.75, 0.80, 0.90,
    # 06    07    08    09    10    11   morning peak: offices and schools
    1.05, 1.20, 1.25, 1.20, 1.10, 1.05,
    # 12    13    14    15
    1.00, 1.00, 1.05, 1.10,
    # 16    17    18    19   evening peak, longer than the morning in Dhaka
    1.20, 1.25, 1.25, 1.20,
    # 20    21    22    23
    1.10, 1.00, 0.90, 0.80,
]
"""
Blocked roads matter in proportion to how many people are trying to use them.

Applied to road_accident, blockade, construction, utility_outage and waterlogging:
all five are obstructions whose cost is congestion. The evening peak is set equal to
the morning one and held for four hours, which is the one asymmetry worth stating —
Dhaka's evening rush is the longer of the two.
"""

_CROWD_DAYTIME: Final[list[float]] = [
    0.70, 0.70, 0.70, 0.70, 0.70, 0.75,
    0.85, 0.95, 1.05, 1.15, 1.20, 1.20,
    1.20, 1.20, 1.20, 1.20,
    1.25, 1.25, 1.15, 1.00,
    0.90, 0.80, 0.75, 0.70,
]
"""
Gatherings are a daytime phenomenon and processions are overwhelmingly afternoon.

Applied to procession and clash. The overnight floor of 0.70 is the lowest in this
module: a crowd flag raised at 3 a.m. is far more likely to be a stale report than a
crowd.
"""

_NIGHT_WEIGHTED: Final[list[float]] = [
    1.20, 1.25, 1.25, 1.20, 1.10, 1.00,
    0.90, 0.85, 0.80, 0.80, 0.80, 0.85,
    0.85, 0.85, 0.85, 0.90,
    0.95, 1.00, 1.05, 1.10,
    1.15, 1.20, 1.25, 1.25,
]
"""
The inverse shape, for the chronic layer only.

`scripts/crime_risk_model.json` is police *crime* statistics, and the thing it
measures is not congestion — it is the kind of incident that is reported more often
after dark. A chronic flag therefore peaks when the traffic profiles trough.

This is the profile most in need of real data, and the one B11 should replace first.
"""

_PROFILE_BY_KIND: Final[dict[IncidentKind, list[float]]] = {
    IncidentKind.ROAD_ACCIDENT: _TRAFFIC_PEAKED,
    IncidentKind.BLOCKADE: _TRAFFIC_PEAKED,
    IncidentKind.CONSTRUCTION: _TRAFFIC_PEAKED,
    IncidentKind.UTILITY_OUTAGE: _TRAFFIC_PEAKED,
    IncidentKind.WATERLOGGING: _TRAFFIC_PEAKED,
    IncidentKind.PROCESSION: _CROWD_DAYTIME,
    IncidentKind.CLASH: _CROWD_DAYTIME,
    IncidentKind.CHRONIC: _NIGHT_WEIGHTED,
    # A fire blocks a road at 4 a.m. exactly as much as at 4 p.m., and `other` is
    # by definition a kind nothing specific is known about. Neither gets a shape.
    IncidentKind.FIRE: _FLAT,
    IncidentKind.OTHER: _FLAT,
}

assert set(_PROFILE_BY_KIND) == set(IncidentKind), (
    "every IncidentKind needs a time profile; a missing one would silently get no "
    "modulation while the table above implies it has some"
)

for _name, _profile in (
    ("_FLAT", _FLAT),
    ("_TRAFFIC_PEAKED", _TRAFFIC_PEAKED),
    ("_CROWD_DAYTIME", _CROWD_DAYTIME),
    ("_NIGHT_WEIGHTED", _NIGHT_WEIGHTED),
):
    assert len(_profile) == 24, f"{_name} has {len(_profile)} multipliers, needs 24"
    assert all(m > 0 for m in _profile), f"{_name} has a non-positive multiplier"


def profile_for(kind: IncidentKind) -> TimeProfile:
    """
    The default hour-of-day profile for a kind, as the contract shape.

    A flag may carry its own `time_profile` — the column exists and D04's extraction
    may fill it per-event — and when it does, that wins. This is the fallback, and it
    is what every flag uses today.
    """
    return TimeProfile(multipliers=list(_PROFILE_BY_KIND[kind]))


def hour_multiplier(profile: TimeProfile | None, at: datetime) -> float:
    """
    The multiplier for the Dhaka-local hour of `at`. 1.0 when there is no profile.

    A naive `at` is read as UTC, matching the endpoint's own handling: every instant
    in this system is UTC by the time it reaches the surface, and silently treating a
    naive value as local time would shift the curve by six hours.
    """
    if profile is None:
        return 1.0
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return profile.multipliers[at.astimezone(DHAKA_TZ).hour]


def decay_anchor(observed_at: datetime, valid_from: datetime | None) -> datetime:
    """
    The instant decay is measured from.

    For an ordinary flag that is `observed_at` — the moment the event happened.

    For a **forward-dated** flag (D09) it is `valid_from`, because a procession
    announced on Tuesday for Friday afternoon did not start fading on Tuesday. Using
    `observed_at` would have the flag arrive already half-decayed, which is the bug
    that would make D09's forward view look broken rather than wrong.

    Note that this returns the anchor even when it is in the future;
    `elapsed_hours()` is what clamps that, and the clamp is where the reasoning about
    a not-yet-started flag lives.
    """
    return valid_from if valid_from is not None else observed_at


def elapsed_hours(anchor: datetime, at: datetime) -> float:
    """
    Hours from `anchor` to `at`, never negative.

    Clamped at zero so that a flag whose window has not opened reads at full
    severity rather than at some amplified value from a negative exponent. That is
    the right answer for a scheduled flag — it is a claim about a future window, and
    in the response it is marked as one by `valid_from` — and D09 is where the map
    renders that difference.
    """
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return max(0.0, (at - anchor).total_seconds() / 3600.0)


def _require_positive_half_life(half_life_hours: float) -> None:
    if half_life_hours <= 0:
        raise ValueError(
            f"half_life_hours must be positive, got {half_life_hours!r}; the database "
            "CHECK risk_flags_half_life_positive says the same thing"
        )


def undecayed_severity(
    *,
    severity_0: float,
    half_life_hours: float,
    observed_at: datetime,
    at: datetime,
    valid_from: datetime | None = None,
) -> float:
    """
    Severity from halving alone, with no time-of-day modulation.

    This is the curve `expires_at` is solved against, so it is the one that decides
    whether a flag is still live. `severity_at()` is what a client sees.
    """
    _require_positive_half_life(half_life_hours)
    hours = elapsed_hours(decay_anchor(observed_at, valid_from), at)
    # float() because `**` on two floats is typed as returning Any, and the strict
    # override on app.scoring.* rejects returning Any from a float function.
    return float(severity_0 * 0.5 ** (hours / half_life_hours))


def severity_at(
    *,
    severity_0: float,
    half_life_hours: float,
    observed_at: datetime,
    at: datetime,
    kind: IncidentKind,
    valid_from: datetime | None = None,
    time_profile: TimeProfile | None = None,
) -> float:
    """
    What a client is served: halving, then the hour-of-day multiplier.

    Clamped to 0-100 because the contract's `severity_now` field is, and a multiplier
    above 1.0 applied to a severity of 95 would otherwise produce a value `RiskFlag`
    refuses to validate — a rejected response rather than a slightly bright pin.

    `time_profile` overrides the kind default when the flag carries one.
    """
    base = undecayed_severity(
        severity_0=severity_0,
        half_life_hours=half_life_hours,
        observed_at=observed_at,
        at=at,
        valid_from=valid_from,
    )
    profile = time_profile if time_profile is not None else profile_for(kind)
    return min(100.0, max(0.0, base * hour_multiplier(profile, at)))


def effective_severity(*, severity_now: float, confidence: float) -> float:
    """
    What a flag is worth to a *decision*: its decayed severity, times its confidence.

    The split matters. `severity_now` answers "how bad is this event right now",
    which is the decay story the flag sheet narrates and the map colours by.
    `confidence` answers "how sure are we that it happened", which is D05's
    verification tier. Multiplying them inside `severity_at()` would collapse two
    different questions into one number and make the sheet's arithmetic
    ("74 when observed, 31 now, 42% remaining") wrong.

    **D06's route scoring must use this, not `severity_now`.** An unconfirmed flag
    should bend a route less than a corroborated one; that is the whole point of
    publishing at reduced weight rather than suppressing.

    `confidence` comes from `app.policy.independence.confidence(status)` and is
    carried on `RiskFlag.confidence`, so callers do not re-derive it.
    """
    return min(100.0, max(0.0, severity_now * confidence))


def expires_at_for(
    *,
    severity_0: float,
    half_life_hours: float,
    observed_at: datetime,
    valid_to: datetime | None = None,
) -> datetime:
    """
    When this flag stops being served. **A mirror of the SQL trigger, not the rule.**

    For anything that goes into `risk_flags`, the database's
    `trg_risk_flags_expires_at` is the authority and this function must not be used
    to supply a value — the trigger would discard it anyway. This exists for
    `SeededRiskSurface`, which serves the fixture with no database in the request
    path and therefore has to derive the column itself.

    The arithmetic, from the trigger:

        severity_0 · 0.5^(t / H) = threshold   =>   t = H · log2(severity_0 / threshold)

    `max(severity_0, threshold)` keeps the logarithm defined and makes a flag born
    below the threshold expire at the instant it was observed, which is correct.

    The `valid_to` wrapper is what lets a procession announced today for tomorrow
    evening survive tonight.
    """
    _require_positive_half_life(half_life_hours)

    hours = (
        half_life_hours
        * math.log(max(severity_0, SERVE_THRESHOLD) / SERVE_THRESHOLD)
        / math.log(2.0)
    )
    decayed_out = observed_at + timedelta(hours=hours)
    if valid_to is not None and valid_to > decayed_out:
        return valid_to
    return decayed_out


def is_live(*, at: datetime, expires_at: datetime, valid_to: datetime | None = None) -> bool:
    """
    Whether a flag should be served at the instant `at`.

    Tests the stored `expires_at` rather than recomputing it: the database derived
    that value and it is the authority. The separate `valid_to` test is not redundant
    — the trigger takes the *later* of the decay-derived instant and `valid_to`, so a
    window that has closed can still sit inside a live decay curve, and a procession
    that finished at noon should not be on the map at midnight.

    This is the Python statement of `_LIVE_PREDICATE` in `surface_db.py`, for the
    seeded surface, which has no SQL to put it in. Status is not tested here because
    the fixture has no rejected or expired rows and `SeededRiskSurface` filters on
    status separately, where that is legible.
    """
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return expires_at > at and (valid_to is None or valid_to > at)
