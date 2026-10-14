"""
`DbNewsCrimeSurface` — the `news_crime_incidents` table behind two reads.

The third sibling of `surface_db.py` and `clusters.py`, and deliberately shaped
like both: a bounding box for the map, a corridor for route scoring, decay applied
in Python on the way out, PostGIS doing the part that needs an index.

## Why this is not a `RiskSurface` either

For the reason `clusters.py` sets out, which applies here with less ambiguity
rather than more. `RiskSurface`'s methods return `RiskFlag`, so satisfying the
protocol means manufacturing a flag — which needs an `IncidentKind` a robbery does
not have and a `mobility_statement` that `policy/framing.py` will refuse to
produce for it. A news crime travels as `NewsCrimeIncident`, consumers name it
explicitly, and the route scorer weighs it with its own constants from
`policy/attribution.py`. Three objects, three shapes, one arithmetic —
`app/scoring/decay.py` is shared by all of them.

## The night profile, and why this surface uses it

Same curve as the community layer. A street crime is reported more often after
dark, and this product's job is telling someone whether to walk down a street at
the hour they are actually asking about. A robbery reported on this corner reads
heavier at 2 a.m. than at 2 p.m., which is both true and the whole point of having
an hour-of-day profile at all.

## Status is derived on read, not stored

The column holds `published` and a `source_count`; the wire says `published` or
`corroborated`. That split is on purpose. Corroboration is a property of how many
*independent publishers* carried the story, which is a policy question answered by
`policy/independence.py` and which could change — collapsing two mastheads of one
house changes the answer for rows already written. Deriving it on read means the
map tells the truth about today's policy rather than about the policy in force on
the day the row was inserted.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.news_crime import NewsCrimeIncident
from app.contracts.risk import SourceRef
from app.policy.attribution import MIN_PUBLISHERS_TO_CORROBORATE
from app.scoring.decay import hour_multiplier, night_weighted_profile, undecayed_severity
from app.scoring.geometry import simplify_for_corridor
from app.scoring.surface_db import POSTGIS_SCHEMA

logger = logging.getLogger(__name__)

__all__ = ["MAX_NEWS_CRIME_PER_READ", "DbNewsCrimeSurface"]

MAX_NEWS_CRIME_PER_READ: Final[int] = 200
"""
A ceiling on any single read, matching `MAX_CLUSTERS_PER_READ` and for the same
reason: these are 250 m objects and a viewport showing more than a couple of
hundred is a viewport nobody can read. A guard against a bad bounding box, not a
pagination scheme.
"""

_CRIME_COLUMNS: Final[str] = f"""
    incident_id,
    category,
    {POSTGIS_SCHEMA}.ST_Y(location::{POSTGIS_SCHEMA}.geometry) AS lat,
    {POSTGIS_SCHEMA}.ST_X(location::{POSTGIS_SCHEMA}.geometry) AS lon,
    radius_m,
    severity_0,
    half_life_hours,
    observed_at,
    source_count,
    sources,
    statement
"""

# Served incidents are live and not yet expired *at the instant asked about*.
# `expires_at` is derived by the database from the decay curve, so this predicate
# and "still above the serve threshold" are the same statement — which is what lets
# an incident retire itself whether or not the sweep has run.
_LIVE_PREDICATE: Final[str] = """
    status = 'published'
    AND expires_at > :at
"""


def _row_to_incident(row: Any, at: datetime) -> NewsCrimeIncident:
    """One row to one `NewsCrimeIncident`, evaluated at the instant `at`."""
    severity_0 = float(row.severity_0)
    base = undecayed_severity(
        severity_0=severity_0,
        half_life_hours=float(row.half_life_hours),
        observed_at=row.observed_at,
        at=at,
    )
    severity_now = min(100.0, max(0.0, base * hour_multiplier(night_weighted_profile(), at)))

    source_count = int(row.source_count)
    return NewsCrimeIncident(
        incident_id=(
            row.incident_id if isinstance(row.incident_id, UUID) else UUID(str(row.incident_id))
        ),
        category=row.category,
        status=(
            "corroborated" if source_count >= MIN_PUBLISHERS_TO_CORROBORATE else "published"
        ),
        latitude=float(row.lat),
        longitude=float(row.lon),
        radius_m=int(row.radius_m),
        severity_now=severity_now,
        observed_at=row.observed_at,
        statement=row.statement,
        source_count=source_count,
        # The citations are the substance of this surface: an attributed claim the
        # reader cannot check is just a claim. A malformed stored ref is skipped
        # rather than failing the whole read — one bad row must not blank the map.
        sources=[ref for ref in (_source_ref(s) for s in (row.sources or [])) if ref],
    )


def _source_ref(raw: Any) -> SourceRef | None:
    if not isinstance(raw, dict):
        return None
    try:
        return SourceRef(
            source_id=str(raw.get("source_id", "")),
            url=str(raw.get("url", "")),
            published_at=raw.get("published_at"),
            title=raw.get("title"),
            snippet=raw.get("snippet"),
        )
    except Exception:  # noqa: BLE001 — a malformed citation is dropped, not fatal
        logger.warning("news_crime: unusable SourceRef in stored sources, skipping")
        return None


class DbNewsCrimeSurface:
    """
    Reads `news_crime_incidents`.

    Holds a session rather than creating one, so a request that reads flags,
    clusters and news crime does all three in one transaction and all three see the
    same snapshot.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def crimes_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        at: datetime,
    ) -> list[NewsCrimeIncident]:
        """
        Live incidents inside a bounding box, at the instant `at`.

        `ST_MakeEnvelope` takes **lon, lat** pairs, the reverse of how the rest of
        this codebase talks about coordinates; hence the named binds.
        """
        statement = text(
            f"""
            SELECT {_CRIME_COLUMNS}
            FROM public.news_crime_incidents
            WHERE {_LIVE_PREDICATE}
              AND {POSTGIS_SCHEMA}.ST_Intersects(
                      location,
                      {POSTGIS_SCHEMA}.ST_MakeEnvelope(
                          :min_lon, :min_lat, :max_lon, :max_lat, 4326
                      )::{POSTGIS_SCHEMA}.geography
                  )
            ORDER BY severity_0 DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            statement,
            {
                "at": at,
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat,
                "limit": MAX_NEWS_CRIME_PER_READ,
            },
        )
        return [_row_to_incident(row, at) for row in result]

    async def crimes_near_path(
        self,
        path: Sequence[tuple[float, float]],
        radius_m: int,
        at: datetime,
    ) -> list[NewsCrimeIncident]:
        """
        Live incidents within `radius_m` of a route, highest current severity first.

        The early return is the same guard the other two surfaces carry, and it is
        not defensive clutter: `ST_MakeLine` of a single point is NULL, `ST_DWithin`
        against NULL is NULL, every row fails the predicate, and the route scores as
        if nothing were near it. The difference between "no incidents" and "the
        question was malformed" matters when the answer tells someone a street is
        clear.
        """
        simplified = simplify_for_corridor(path)
        if len(simplified) < 2:
            return []

        # WKT rather than a bound array: asyncpg cannot adapt a list of tuples to a
        # PostGIS type. Built from floats already validated as coordinates by the
        # request schema, so there is no injection surface.
        line_wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in simplified) + ")"

        statement = text(
            f"""
            SELECT {_CRIME_COLUMNS}
            FROM public.news_crime_incidents
            WHERE {_LIVE_PREDICATE}
              AND {POSTGIS_SCHEMA}.ST_DWithin(
                      location,
                      {POSTGIS_SCHEMA}.ST_SetSRID(
                          {POSTGIS_SCHEMA}.ST_GeomFromText(:line_wkt), 4326
                      )::{POSTGIS_SCHEMA}.geography,
                      :radius_m
                  )
            ORDER BY severity_0 DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            statement,
            {
                "at": at,
                "line_wkt": line_wkt,
                "radius_m": radius_m,
                "limit": MAX_NEWS_CRIME_PER_READ,
            },
        )
        incidents = [_row_to_incident(row, at) for row in result]
        incidents.sort(key=lambda incident: incident.severity_now, reverse=True)
        return incidents
