"""
The chronic baseline layer, from real Bangladesh Police unit statistics.

`scripts/crime_risk_model.json` holds 16 rows derived from published police
reported-crime totals: one per metropolitan unit (DMP, CMP, …) and one per range
(Dhaka Range, Chittagong Range, …), each with a centre, a radius in kilometres and
a `normalized_risk` on a 0-100 scale. This module turns the useful subset of that
into `chronic` risk flags.

Why this exists at all
----------------------
The concept document's §5 decay table includes a chronic blackspot — a place that is
persistently worse, measured over months rather than hours. The real implementation
is newspaper archive mining at scale (B11, source sprint S24). That is weeks of
work. This is an afternoon, it uses data already in the repository, and it gives the
surface a genuine long-half-life layer underneath the short-lived event flags. When
B11 lands it replaces this, and the 90-day half-life is the same either way so the
layer does not change character.

Two decisions that keep it honest
---------------------------------
**1. Ranges are dropped; only metropolitan units are emitted.**
`Dhaka Range` is an administrative aggregate with a 100 km radius and a
`normalized_risk` of 100.0 — it is the maximum of the whole dataset, and it
geographically *contains* DMP, whose own figure is 58.9. Emitting both would put two
chronic flags over every point in Dhaka and count the same reported crimes twice,
and the larger one would blanket the entire map at maximum severity. So the rule is:
**the most specific unit covering a point wins, and the aggregate is not a second
opinion.** Eight `… Range` rows are skipped. Seven metropolitan units remain, of
which exactly one, DMP, is in the demo zone.

This is the same mistake `route_service._get_regional_risk()` makes today — it takes
the `max` across every overlapping unit, so a Dhaka route scores 100 from the range
row rather than 58.9 from the city row. D06 deletes that method; this is the
replacement, and the reason the double-count note in DEMO_PLAN.md D02 is there.

**2. A chronic flag is not an incident, and its statement says so.**
The text comes from `framing.py` like every other flag's, with
`MobilityImpact.DELAY_LIKELY` and the `chronic` kind qualifier, which reads
"Delay likely near Dhaka Metropolitan, reported repeatedly over time." That is a
mobility claim about a 20 km police-unit area, which is what the data supports. It is
not "Dhaka is dangerous", and the framing guard would reject that sentence anyway.

What a judge should be told about this layer
--------------------------------------------
It is real published data at police-unit granularity, which is coarse — one flag for
a 20 km radius. It is a baseline, not a blackspot map. Saying that plainly is a
better answer than implying street-level chronic detection the data cannot support,
and the next sprint that makes it street-level is named (B11).
"""

import json
import logging
from pathlib import Path
from typing import Any, Final, NamedTuple

from app.contracts.risk import IncidentKind, MobilityImpact
from app.policy.framing import to_mobility_statement
from app.scoring.kinds import defaults_for

logger = logging.getLogger(__name__)

MODEL_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "crime_risk_model.json"
)

CHRONIC_EVENT_KEY_PREFIX: Final[str] = "seed-chronic-"
"""
Chronic rows are seeded rows.

They share the `seed-` prefix so `seed_risk_flags.py --clear` removes them with
everything else it owns, and carry `chronic-` after it so they can be told apart
from the hand-built event fixture in a query.
"""

MAX_RADIUS_M: Final[int] = 20_000
"""
The `risk_flags_radius_sane` CHECK ceiling, mirrored.

DMP's own radius is exactly 20 km, so this clamp is load-bearing rather than
defensive: one more kilometre in the source data and the insert would fail on a
constraint instead of being visibly clamped here.
"""

_RANGE_SUFFIX: Final[str] = " Range"


class ChronicUnit(NamedTuple):
    """One police unit, as a flag-shaped row."""

    unit: str
    event_key: str
    lat: float
    lon: float
    radius_m: int
    severity_0: float


def _slug(unit: str) -> str:
    return unit.lower().replace(" ", "-")


def chronic_units(model_path: Path | None = None) -> list[ChronicUnit]:
    """
    The metropolitan units in the model, as rows ready to become `chronic` flags.

    Sorted by unit name so the output is stable: an unstable order would make the
    generated seed SQL churn in diffs for no reason.

    Raises rather than returning an empty list if the model is missing or has no
    usable rows. A chronic layer that silently does not exist is exactly the kind of
    gap that gets discovered on stage.
    """
    path = model_path or MODEL_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"chronic model not found at {path}. It ships in the repository; if it is "
            "missing, the chronic baseline layer cannot be built."
        )

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    units: list[ChronicUnit] = []

    for unit, data in sorted(raw.items()):
        # See decision 1 in the module docstring. A range contains the metropolitan
        # unit inside it and would double-count it.
        if unit.endswith(_RANGE_SUFFIX):
            continue

        location = data.get("location") or {}
        lat, lon = location.get("lat"), location.get("lon")
        radius_km = location.get("radius_km")
        severity = data.get("normalized_risk")

        if lat is None or lon is None or radius_km is None or severity is None:
            # Not raised: a partial row is a data problem in one unit, not a reason
            # to serve no chronic layer at all. Named so it is findable.
            logger.warning("chronic: skipping %r — incomplete row in the model", unit)
            continue

        units.append(
            ChronicUnit(
                unit=unit,
                event_key=f"{CHRONIC_EVENT_KEY_PREFIX}{_slug(unit)}",
                lat=float(lat),
                lon=float(lon),
                radius_m=min(int(float(radius_km) * 1000), MAX_RADIUS_M),
                severity_0=float(severity),
            )
        )

    if not units:
        raise ValueError(
            f"{path} produced no chronic units. Every row was a range or incomplete, "
            "which means the model's shape has changed."
        )
    return units


def chronic_rows(now: Any, model_path: Path | None = None) -> list[dict[str, Any]]:
    """
    Chronic units as insert-shaped dicts, matching what `seed_risk_flags.py` builds.

    `now` is the observation instant. Chronic flags are observed *now* rather than at
    some point in the past because the statistic they come from is a current
    description of a place, not a report of an event — and with a 90-day half-life,
    backdating would only make the layer arbitrarily weaker.

    `status` is `unconfirmed` and `source_count` is 1. It would be tempting to call a
    government statistic `confirmed`, and the CHECK constraint would reject it: one
    source cannot produce a confirmed flag. That rule has no exception for official
    data, and leaving the layer honestly unconfirmed is the correct reading of it.

    `mobility_statement` is produced here by `framing.py`, like every other flag's.
    """
    half_life = defaults_for(IncidentKind.CHRONIC).half_life_hours

    return [
        {
            "event_key": unit.event_key,
            "kind": IncidentKind.CHRONIC.value,
            "status": "unconfirmed",
            "lat": unit.lat,
            "lon": unit.lon,
            "radius_m": unit.radius_m,
            "severity_0": unit.severity_0,
            "half_life_hours": half_life,
            "observed_at": now,
            "valid_from": None,
            "valid_to": None,
            "source_count": 1,
            "sources": [
                {
                    "source_id": "bd_police_statistics",
                    "url": "https://www.police.gov.bd/en/crime_statistic_comparative_statement",
                    "published_at": None,
                    "title": f"Reported crime statistics — {unit.unit}",
                    "snippet": (
                        "Police-unit reported-crime totals, normalised to 0-100. "
                        "Unit-level granularity; see app/scoring/chronic.py."
                    ),
                }
            ],
            "mobility_statement": to_mobility_statement(
                kind=IncidentKind.CHRONIC,
                impact=MobilityImpact.DELAY_LIKELY,
                place=_display_place(unit.unit),
            ),
        }
        for unit in chronic_units(model_path)
    ]


_UNIT_DISPLAY_NAMES: Final[dict[str, str]] = {
    "DMP": "Dhaka Metropolitan",
    "CMP": "Chattogram Metropolitan",
    "KMP": "Khulna Metropolitan",
    "RMP": "Rajshahi Metropolitan",
    "BMP": "Barishal Metropolitan",
    "SMP": "Sylhet Metropolitan",
    "GMP": "Gazipur Metropolitan",
    "RPMP": "Rangpur Metropolitan",
}
"""
Acronym to the name a user can read.

"Delay likely near DMP" is not a sentence anyone outside the police service parses,
and the mobility statement is the one string a user sees. Unmapped acronyms fall
through unchanged rather than being dropped — a readable-but-terse flag beats no
flag.
"""


def _display_place(unit: str) -> str:
    return _UNIT_DISPLAY_NAMES.get(unit, unit)
