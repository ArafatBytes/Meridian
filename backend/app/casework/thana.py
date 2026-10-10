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
placeholder address and one placeholder number repeated across every row, so
this module does not read them and nothing downstream can display them
(DEMO_PLAN 7.2, closed 2026-10-10).
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

# Bangladesh, generously bounded. A coordinate outside this is a bug upstream —
# a swapped lat/lon, a zero from a failed fix — and naming a thana for it would
# put a wrong station on a legal document with no hint that anything went wrong.
LAT_RANGE: Final = (20.0, 27.0)
LON_RANGE: Final = (88.0, 93.0)

EARTH_RADIUS_KM: Final = 6371.0


@dataclass(frozen=True, slots=True)
class Thana:
    name: str
    district: str
    distance_km: float


@lru_cache(maxsize=1)
def _stations() -> tuple[tuple[str, str, float, float], ...]:
    """(name, district, lat, lon) for every usable row. Read once."""
    rows: list[tuple[str, str, float, float]] = []
    if not CSV_PATH.exists():
        logger.error("police_stations.csv not found at %s — no thana lookup", CSV_PATH)
        return ()
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append((name, (row.get("district") or "").strip(), lat, lon))
    logger.info("Loaded %d police stations for thana lookup", len(rows))
    return tuple(rows)


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
    """
    if not (LAT_RANGE[0] <= latitude <= LAT_RANGE[1]):
        logger.warning("latitude %s is outside Bangladesh — no thana named", latitude)
        return None
    if not (LON_RANGE[0] <= longitude <= LON_RANGE[1]):
        logger.warning("longitude %s is outside Bangladesh — no thana named", longitude)
        return None

    best: Thana | None = None
    for name, district, lat, lon in _stations():
        distance = _haversine_km(latitude, longitude, lat, lon)
        if best is None or distance < best.distance_km:
            best = Thana(name=name, district=district, distance_km=round(distance, 2))
    return best


def all_thana_names() -> tuple[str, ...]:
    """Every station name, for the review screen's "wrong thana?" picker."""
    return tuple(sorted({name for name, _, _, _ in _stations()}))
