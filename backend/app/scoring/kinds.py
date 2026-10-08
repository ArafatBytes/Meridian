"""
Per-kind defaults — the reviewed table S19 asks for.

One place that answers "how long does a fire matter for, and over how big an
area". Every number here is a judgement call, so each one is written down with
the reason rather than left as a literal in whichever module needed it first.

The source is the concept document §5.6 decay table, which gives half-lives as
ranges rather than values: a road accident is "about an hour", a fire "three to
four hours", a clash "six to twelve", an announced event "its duration", a chronic
blackspot "months". Those ranges are the specification; the single values below are
this project's reading of them, and the range is recorded in the comment so a later
change is an argument about the reading rather than a guess at the intent.

Who reads this table
--------------------
* `data/fixtures/risk_flags.json` — a fixture entry gives `kind` and may omit
  `half_life_hours` and `radius_m`; the loader fills them from here. That is what
  keeps a 200-entry fixture readable, and it means the fixture cannot drift from
  the reviewed values by a typo.
* `app/scoring/chronic.py` — the chronic baseline's half-life.
* D04's Live Risk Agent, when an extracted incident carries no severity hint.

What it deliberately does not do
--------------------------------
Nothing here is applied to a flag that already has a value. A flag extracted from
news with a stated severity keeps it. This is a table of defaults, not of
overrides.
"""

from typing import Final, NamedTuple

from app.contracts.risk import IncidentKind


class KindDefaults(NamedTuple):
    """
    What a flag of this kind looks like when nothing more specific is known.

    `severity_0` is the value for a flag of ordinary magnitude. The fixture and
    D04's extraction both vary it; it exists so that neither has to invent a number
    for a kind it has not thought about.
    """

    half_life_hours: float
    radius_m: int
    severity_0: float


KIND_DEFAULTS: Final[dict[IncidentKind, KindDefaults]] = {
    # "About an hour" — a collision is cleared and the queue drains. The shortest
    # half-life in the table, and the one that makes decay visible in a demo.
    IncidentKind.ROAD_ACCIDENT: KindDefaults(1.0, 250, 45.0),
    # "Three to four hours." Taken at 3.5: fire service response plus the time the
    # diversion stays in place. Radius is wider than an accident because the
    # cordon is, not because the fire is.
    IncidentKind.FIRE: KindDefaults(3.5, 400, 70.0),
    # "Six to twelve hours." Taken at 8 rather than the midpoint: the mobility
    # effect outlasts the event itself, and under-stating it leaves a road
    # reported open while it is still closed.
    IncidentKind.CLASH: KindDefaults(8.0, 600, 75.0),
    # Not in the §5.6 table. Sits below a clash: a blockade is usually announced,
    # localised and ends at a known time, and most of them carry a valid_to that
    # overrides this anyway.
    IncidentKind.BLOCKADE: KindDefaults(6.0, 500, 65.0),
    # "An announced event lasts its duration" — so for a procession the half-life
    # is mostly irrelevant: `valid_to` is what holds it alive and what retires it
    # (the expires_at trigger takes the later of the two). 4 hours is the tail
    # after the window closes, for the crowd to disperse.
    IncidentKind.PROCESSION: KindDefaults(4.0, 700, 55.0),
    # Dhaka waterlogging after heavy rain persists most of a day and covers a
    # neighbourhood rather than a junction. Severity is moderate because it is a
    # delay, not a closure, most of the time.
    IncidentKind.WATERLOGGING: KindDefaults(12.0, 800, 40.0),
    # Works last weeks. 30 days of half-life, and a narrow radius because the
    # obstruction is a specific stretch of road. Low severity: it is a known,
    # routable condition rather than an event.
    IncidentKind.CONSTRUCTION: KindDefaults(720.0, 300, 30.0),
    IncidentKind.UTILITY_OUTAGE: KindDefaults(24.0, 400, 25.0),
    # "Months." 90 days, which is the same figure B11's archive mining will use,
    # so the chronic layer does not change character when its source changes.
    # Radius and severity are always supplied by the caller for this kind — a
    # chronic flag's extent comes from the data it was derived from — so these two
    # are a floor, not a description.
    IncidentKind.CHRONIC: KindDefaults(2160.0, 2000, 40.0),
    IncidentKind.OTHER: KindDefaults(4.0, 400, 35.0),
}

assert set(KIND_DEFAULTS) == set(IncidentKind), (
    "KIND_DEFAULTS must cover every IncidentKind: a kind with no entry would fall "
    "back to whatever the caller happened to pass, which is the drift this table exists "
    "to prevent."
)


def defaults_for(kind: IncidentKind) -> KindDefaults:
    """The reviewed defaults for one kind. Total over `IncidentKind` by the assert above."""
    return KIND_DEFAULTS[kind]


SEVERITY_HINT_FACTOR: Final[dict[str, float]] = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.3,
}
"""
How an extracted `severity_hint` moves a kind's baseline severity (D04).

Mild on purpose. The hint is a free-tier model's reading of one article, and the
baseline is the reviewed value — so the hint nudges rather than decides. 0.6 keeps a
"low" fire (70 → 42) above a "medium" road accident's 45 less often than not, which
matches the intuition that a minor fire still closes more road than a minor
collision. 1.3 caps out at 97.5 for the most severe baseline (clash, 75), inside the
0-100 scale with no clamping needed for any kind.
"""


def severity_for(kind: IncidentKind, hint: str | None) -> float:
    """A kind's baseline severity, nudged by an extracted hint. No hint means baseline."""
    factor = SEVERITY_HINT_FACTOR.get(hint, 1.0) if hint else 1.0
    return min(100.0, defaults_for(kind).severity_0 * factor)
