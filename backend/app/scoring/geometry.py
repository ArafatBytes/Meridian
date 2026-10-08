"""
Corridor geometry, shared by both risk surfaces.

D06, defect 8. `DbRiskSurface.flags_near_path` asks PostGIS and
`SeededRiskSurface.flags_near_path` does the arithmetic in Python, but they must agree,
because `tests/invariants/test_surfaces_agree.py` compares their answers and the offline
demo depends on the seeded one being a faithful stand-in.

Two things therefore live here rather than in either surface:

* **`simplify_for_corridor`** — both surfaces must thin the path *identically*. Two
  simplifications would make the invariant test fail over something that is not a
  disagreement about risk.
* **`distance_to_segment_m`** — point-to-segment, which is what `ST_DWithin` against a
  LINESTRING measures. The seeded surface has to match that, not approximate it.

No configuration, no database, no imports from the rest of `app.scoring` — so this is
importable from a test or a script with nothing set up, for the same reason
`factory.py` is kept out of the package `__init__`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

__all__ = [
    "CORRIDOR_SIMPLIFY_M",
    "distance_to_segment_m",
    "haversine_m",
    "simplify_for_corridor",
]

_EARTH_RADIUS_M: Final[float] = 6_371_000.0

_METRES_PER_DEGREE_LAT: Final[float] = 111_320.0
"""
One degree of latitude in metres.

Constant enough for this purpose: it varies by about 0.6% between the equator and the
poles, and every use here is a local projection over a few hundred metres in Dhaka.
"""


CORRIDOR_SIMPLIFY_M: Final[int] = 120
"""
Minimum spacing between retained path points, in metres.

An OSRM `overview=full` geometry is several hundred points for a Dhaka crossing and
consecutive ones are metres apart. Keeping them all makes a LINESTRING that PostGIS has
to work harder over, and makes the seeded surface's point-to-segment loop hundreds of
times longer, for a corridor shape that is indistinguishable at any `radius_m` worth
asking about.

**120 m is well inside the smallest radius the scoring engine uses** — a terminal flag is
300 m — so thinning cannot move a flag across the threshold and change a verdict.
"""


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres. Mean Earth radius; good to ~0.5%."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    h = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return float(2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h))))


def simplify_for_corridor(
    path: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    Drop path points closer than `CORRIDOR_SIMPLIFY_M` to the last one kept.

    **Deliberately not Douglas-Peucker.** This is distance-thinning: every retained point
    is an original point, so the line cannot move. A shape-preserving simplifier would be
    better for *drawing* and worse here, because it is allowed to cut a corner — and a cut
    corner is a stretch of road that silently stops being tested for flags.

    The first and last points are always kept, so the corridor still starts where the
    traveller starts and ends where they arrive.

    >>> simplify_for_corridor([(23.70, 90.40), (23.70, 90.40), (23.80, 90.40)])
    [(23.7, 90.4), (23.8, 90.4)]
    """
    points = [(float(lat), float(lon)) for lat, lon in path]
    if len(points) < 3:
        return points

    kept = [points[0]]
    for point in points[1:-1]:
        if haversine_m(kept[-1][0], kept[-1][1], point[0], point[1]) >= CORRIDOR_SIMPLIFY_M:
            kept.append(point)
    kept.append(points[-1])
    return kept


def distance_to_segment_m(
    lat: float,
    lon: float,
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    """
    Distance from a point to a line *segment*, in metres.

    Point-to-segment, not point-to-vertex, and that distinction is why this exists. A
    route thinned to one point every 120 m, tested only at its vertices, would miss
    anything beside the middle of a straight run — which is exactly where a long road's
    flags sit. `ST_DWithin` against a LINESTRING measures to the segment, so the seeded
    surface has to as well or the two surfaces disagree.

    Projects into a local equirectangular plane scaled by `cos(latitude)` before doing the
    algebra. Over a segment of a few hundred metres in Dhaka that is accurate to well
    under a metre, and it avoids a spherical cross-track formula whose edge cases — a
    zero-length segment, a point past an endpoint — are easy to get subtly wrong.
    """
    lat_ref = math.radians((lat_a + lat_b) / 2.0)
    scale_x = math.cos(lat_ref) * _METRES_PER_DEGREE_LAT
    scale_y = _METRES_PER_DEGREE_LAT

    px, py = lon * scale_x, lat * scale_y
    ax, ay = lon_a * scale_x, lat_a * scale_y
    bx, by = lon_b * scale_x, lat_b * scale_y

    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        # A zero-length segment is a point. Returning the point distance rather than
        # dividing by zero matters because a simplified path can legitimately contain
        # two identical consecutive points when the route doubles back on itself.
        return float(math.hypot(px - ax, py - ay))

    # Clamped: 0 and 1 are the endpoints, so a point beyond either end measures to that
    # end rather than to the infinite line the segment lies on.
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return float(math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
