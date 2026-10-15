"""
Which police station does this incident belong to? D08, ADR 0007.

    station = nearest_thana(23.7465, 90.3760)
    station.name      # "Dhanmondi Police Station"
    station.district  # "Dhaka"

Nearest by straight-line distance over `backend/police_stations.csv`. That is
not how jurisdiction actually works — thana boundaries are polygons drawn by
people, not Voronoi cells around a point — so this names the station the user
should *check*, and the review screen lets them change it. Getting the thana
wrong is the single most likely way a GD comes back rejected, and it is also
the easiest thing for the person standing there to correct.

**The name is all we take.** That CSV's `email` and `phone` columns hold one
address and one number repeated across every row, so this module does not read
them and nothing downstream can display them (DEMO_PLAN 7.2, closed 2026-10-10).

## Dhaka city only, and why a station can be named but not located — defect 17

The CSV covers all of Bangladesh: **607 rows, 560 of them `legacy — unverified`.**
Two filters are applied, for two different reasons.

**Geography.** Only `district == "Dhaka"` is loaded, which is exactly the 51 DMP
thanas — checked, the column contains no Dhaka-district upazila stations
(no Savar, Keraniganj, Dhamrai, Nawabganj, Dohar). This app's map, gazetteer and
flags are Dhaka city; a Sherpur thana in the picker was noise at best, and
`nearest_thana` could return one for a bad coordinate.

**Coordinate quality.** Five of those 51 rows are `legacy — unverified` and their
coordinates do not survive checking *against the file's own trusted rows*:

| row | its coordinate sits | which is wrong because |
|---|---|---|
| Turag | 1.7 km from **Rampura** | Turag is the far north, by Tongi |
| Hatirjheel | 4.4 km from **Pallabi** | Hatirjheel is the central lake |
| Cantonment | 1.4 km from **Shah Ali** | Shah Ali is Mirpur |
| Bhashantek | 2.4 km from **Khilkhet** | Bhashantek is Mirpur |
| Uttarkhan | 3.8 km from **Uttara** | adjacent — plausible, but unverified |

So those five are **nameable but not locatable**: their names stay in the
review-screen picker, because somebody filing a GD in Turag needs to find
"Turag Police Station" in the list, and excluding them would silently remove a
real thana. Their coordinates are kept out of the distance ranking, because a
pin 4 km into the wrong neighbourhood is how a GD gets addressed to the wrong
officer-in-charge. **44 locatable, 49 nameable** — 51 Dhaka rows, less the two
exact duplicates below, less the five unverified coordinates for ranking only.

This is deliberately driven by the file's own `coord_source` column rather than
by anybody's opinion about Dhaka geography. If a row is upgraded from
`legacy — unverified`, it becomes locatable with no code change.

## Duplicates

The DMP rows carry two spellings of two thanas — `Gandaria`/`Gendaria` and
`Bhatara`/`Vatara`, each pair sharing one coordinate — plus exact duplicates of
`Hazaribagh` and `Vatara`. Exact duplicates are dropped. **The spelling variants
are kept**, because the picker is searched by the name the user knows, and
dropping one would make that thana unfindable for half the people who need it.
Ranking is made deterministic by sorting instead: co-located variants always
resolve to the same name, so the same incident never yields `Gandaria` one run
and `Gendaria` the next on a signed document.
"""
from __future__ import annotations

import csv
import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

CSV_PATH: Final = Path(__file__).resolve().parents[2] / "police_stations.csv"

# Dhaka city. The `district` column holds exactly the DMP thanas for this value.
DHAKA_CITY_DISTRICT: Final = "Dhaka"

# The file's own label for a coordinate nobody checked. See the module docstring
# for what these five rows actually point at.
UNVERIFIED_COORDS: Final = "legacy — unverified"

# Bangladesh, generously bounded. A coordinate outside this is a bug upstream —
# a swapped lat/lon, a zero from a failed fix — and naming a thana for it would
# put a wrong station on a legal document with no hint that anything went wrong.
LAT_RANGE: Final = (20.0, 27.0)
LON_RANGE: Final = (88.0, 93.0)

# Beyond this, the nearest DMP thana is not plausibly your thana.
#
# Derived, not picked: sweeping a 101x101 grid over the project's own gazetteer
# box (90.30,23.66,90.54,23.94), the furthest any point in Dhaka sits from a
# locatable station is **14.6 km**, at the box's north-east corner. 25 km covers
# that with room and still refuses the thing worth refusing — Chattogram is
# 200.9 km from the nearest DMP station and used to be answered with a Dhaka
# thana name, confidently.
MAX_PLAUSIBLE_KM: Final = 25.0

EARTH_RADIUS_KM: Final = 6371.0


@dataclass(frozen=True, slots=True)
class Thana:
    name: str
    district: str
    distance_km: float


def _dhaka_city_rows() -> list[dict[str, str]]:
    """Every `district == "Dhaka"` row, parsed. Contact columns are not read."""
    if not CSV_PATH.exists():
        logger.error("police_stations.csv not found at %s — no thana lookup", CSV_PATH)
        return []
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (row.get("district") or "").strip() == DHAKA_CITY_DISTRICT
        ]


@lru_cache(maxsize=1)
def _locatable() -> tuple[tuple[str, str, float, float], ...]:
    """
    `(name, district, lat, lon)` for ranking — Dhaka city, trusted coords only.

    Sorted by name so that two co-located spelling variants always resolve to the
    same one. Without the sort the winner is whichever `csv.DictReader` reached
    first, which is stable only until somebody re-exports the file.
    """
    rows: list[tuple[str, str, float, float]] = []
    seen: set[tuple[str, float, float]] = set()
    for row in _dhaka_city_rows():
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if (row.get("coord_source") or "").strip() == UNVERIFIED_COORDS:
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        key = (name, lat, lon)
        if key in seen:  # exact duplicate row
            continue
        seen.add(key)
        rows.append((name, (row.get("district") or "").strip(), lat, lon))
    rows.sort()
    logger.info("Thana lookup: %d locatable Dhaka city stations", len(rows))
    return tuple(rows)


@lru_cache(maxsize=1)
def _nameable() -> tuple[str, ...]:
    """
    Every Dhaka city station name, including the five with untrusted coordinates.

    A name in this list is not a claim about where the station is — only that it
    exists and the user may need to pick it.
    """
    names = sorted({(row.get("name") or "").strip() for row in _dhaka_city_rows()} - {""})
    logger.info("Thana picker: %d Dhaka city station names", len(names))
    return tuple(names)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def nearest_thana(latitude: float, longitude: float) -> Thana | None:
    """
    The closest station to a point, or None when we should not guess.

    None means exactly one thing: we do not know. The caller shows the user an
    empty thana field to fill in rather than a confident wrong answer, because
    an application addressed to the wrong officer-in-charge is worse than one
    addressed to nobody yet.

    Three ways to get `None`, and the third is new in defect 17:

    * a latitude outside Bangladesh,
    * a longitude outside Bangladesh,
    * **a point more than `MAX_PLAUSIBLE_KM` from any Dhaka city station.**
      The station list is Dhaka-only now, so without this a GD filed from
      Chattogram would be addressed to whichever DMP thana happened to be
      closest, 200 km away, with no hint anything was wrong. Silence is the
      correct answer there.
    """
    if not (LAT_RANGE[0] <= latitude <= LAT_RANGE[1]):
        logger.warning("latitude %s is outside Bangladesh — no thana named", latitude)
        return None
    if not (LON_RANGE[0] <= longitude <= LON_RANGE[1]):
        logger.warning("longitude %s is outside Bangladesh — no thana named", longitude)
        return None

    best: Thana | None = None
    for name, district, lat, lon in _locatable():
        distance = _haversine_km(latitude, longitude, lat, lon)
        if best is None or distance < best.distance_km:
            best = Thana(name=name, district=district, distance_km=round(distance, 2))

    if best is not None and best.distance_km > MAX_PLAUSIBLE_KM:
        logger.warning(
            "nearest Dhaka city thana to (%s, %s) is %s at %.1f km — outside the "
            "city, so no thana named",
            latitude,
            longitude,
            best.name,
            best.distance_km,
        )
        return None
    return best


def all_thana_names() -> tuple[str, ...]:
    """
    Every Dhaka city station name, for the review screen's "wrong thana?" picker.

    Includes the five whose coordinates are untrusted — being unable to place a
    station is no reason to stop the user naming it. See the module docstring.
    """
    return _nameable()
