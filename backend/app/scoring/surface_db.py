"""
`DbRiskSurface` — the `risk_flags` table behind the `RiskSurface` protocol.

Two reads: a bounding box for the map, and a radius for everything that asks
"what is near here". D02 adds `SeededRiskSurface` beside this one and the Risk
Scoring Engine on top of both.

The reason D01 builds this rather than querying the table from the endpoint is
that the seam has to exist before there are two implementations — otherwise D02's
fixture surface arrives with nowhere to plug in and the endpoint gets rewritten.

Raw SQL, not the ORM
--------------------
These queries are PostGIS: `ST_Intersects` against a `geography` column with a GiST
index, `ST_DWithin` in metres, `ST_X`/`ST_Y` to read coordinates back. None of that
is expressible through the declarative models without geoalchemy2 constructs that
read worse than the SQL and type worse too. Every statement is fully
parameterised; no caller value is interpolated.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.risk import IncidentKind, RiskFlag, SourceRef, TimeProfile
from app.policy.independence import confidence
from app.scoring.decay import severity_at
from app.scoring.geometry import simplify_for_corridor

POSTGIS_SCHEMA: Final[str] = "extensions"
"""
Where PostGIS functions live.

Supabase installs PostGIS into `extensions` rather than `public`, and the
project's `SCHEMA.sql` follows that. Every PostGIS call below is schema-qualified
because this module does not control the connection's `search_path`, and an
unqualified `ST_Intersects` fails with a bewildering "function does not exist" the
first time a pooled connection comes back with a different path. One constant, so
moving it is one edit.
"""

MAX_FLAGS_PER_READ: Final[int] = 500
"""
A ceiling on any single read. The Dhaka fixture is ~200 flags (D02) and a map
viewport cannot usefully draw more than a few hundred pins, so this is a guard
against a bad bounding box returning the whole table, not a pagination scheme.
"""

# Both queries select exactly this shape, and `_row_to_flag` depends on all of it
# being present, so it lives in one place.
_FLAG_COLUMNS: Final[str] = f"""
    flag_id,
    event_key,
    kind,
    status,
    {POSTGIS_SCHEMA}.ST_Y(location::{POSTGIS_SCHEMA}.geometry) AS lat,
    {POSTGIS_SCHEMA}.ST_X(location::{POSTGIS_SCHEMA}.geometry) AS lon,
    radius_m,
    severity_0,
    half_life_hours,
    observed_at,
    expires_at,
    valid_from,
    valid_to,
    source_count,
    sources::text  AS sources_json,
    mobility_statement,
    confirmed_at,
    time_profile::text AS time_profile_json
"""

# Served flags are live and not yet expired *at the instant asked about*.
#
# `expires_at` is derived by the database and already accounts for a forward-dated
# flag's validity window, so it is the main expiry test. The separate `valid_to`
# test is not redundant: the trigger sets expires_at to the LATER of the
# decay-derived instant and valid_to, so a window that has closed can still sit
# inside a live decay curve.
#
# `valid_from` is the floor (D09): a scheduled flag is not served before its window
# opens. The reasoning is in `decay.is_live`, which is the Python mirror of this
# predicate and must keep saying the same thing.
_LIVE_PREDICATE: Final[str] = """
    status IN ('unconfirmed', 'confirmed')
    AND expires_at > :at
    AND (valid_from IS NULL OR valid_from <= :at)
    AND (valid_to IS NULL OR valid_to > :at)
"""


def _row_to_flag(row: Any, at: datetime) -> RiskFlag:
    """
    One database row to one `RiskFlag`, evaluated at the instant `at`.

    `sources` and `time_profile` arrive as text and are parsed here rather than
    relying on the driver: with raw SQL, asyncpg returns `jsonb` as a string, and
    whether SQLAlchemy intercepts that depends on column typing this query does not
    declare. Casting to text in SQL and parsing here behaves the same everywhere.

    `severity_now` is computed in Python rather than in the SQL above, which is a
    departure from S20's "decay applied at query time in PostGIS". The reason is the
    time-of-day profile: it is a 24-element array lookup against the Dhaka-local hour,
    and expressing that in SQL means either a `CASE` with 24 branches or a jsonb index
    into a column that is null on every row today, in both cases duplicating
    `app/scoring/decay.py` in a second language. The decay arithmetic already has two
    implementations it cannot avoid (Python for the seeded surface, SQL for
    `expires_at`); adding a third, in the hot path, to save an exponent per row on a
    result set capped at 500 is a bad trade.

    What PostGIS still does at query time is the part that needs an index: the spatial
    test and the liveness filter. Rows that have decayed below the serve threshold never
    leave the database, because `expires_at` encodes exactly that point.
    """
    raw_sources: list[dict[str, Any]] = json.loads(row.sources_json or "[]")
    raw_profile: dict[str, Any] | None = (
        json.loads(row.time_profile_json) if row.time_profile_json else None
    )
    kind = IncidentKind(row.kind)
    time_profile = TimeProfile(**raw_profile) if raw_profile else None

    return RiskFlag(
        flag_id=row.flag_id if isinstance(row.flag_id, UUID) else UUID(str(row.flag_id)),
        event_key=row.event_key,
        kind=kind,
        status=row.status,
        lat=float(row.lat),
        lon=float(row.lon),
        radius_m=int(row.radius_m),
        severity_0=float(row.severity_0),
        severity_now=severity_at(
            severity_0=float(row.severity_0),
            half_life_hours=float(row.half_life_hours),
            observed_at=row.observed_at,
            at=at,
            kind=kind,
            valid_from=row.valid_from,
            time_profile=time_profile,
        ),
        half_life_hours=float(row.half_life_hours),
        observed_at=row.observed_at,
        expires_at=row.expires_at,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        source_count=int(row.source_count),
        sources=[SourceRef(**s) for s in raw_sources],
        mobility_statement=row.mobility_statement,
        time_profile=time_profile,
        confirmed_at=row.confirmed_at,
        # D05. Derived here rather than stored, for the same reason `severity_now` is:
        # the weight an unconfirmed flag carries is a policy decision, and a surface is
        # the only place allowed to turn policy into a field.
        confidence=confidence(row.status),
    )


class DbRiskSurface:
    """
    Reads `risk_flags`. Satisfies `app.contracts.surface.RiskSurface`.

    Holds a session rather than creating one, so a request that reads the surface
    and writes something else does both in one transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def flags_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        at: datetime,
    ) -> list[RiskFlag]:
        """
        Live flags whose location falls inside a bounding box, at the instant `at`.

        `ST_Intersects` on a `geography` column uses the GiST index — verified
        against PostGIS 16, where the plan is an index scan rather than a
        sequential one. The `&&` operator would too, but lives in the PostGIS
        schema and is awkward to qualify.

        Note the argument order: `ST_MakeEnvelope` takes **lon, lat** pairs, the
        reverse of how every caller in this codebase talks about coordinates.
        Hence the named bind parameters.
        """
        statement = text(
            f"""
            SELECT {_FLAG_COLUMNS}
            FROM public.risk_flags
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
                "limit": MAX_FLAGS_PER_READ,
            },
        )
        return [_row_to_flag(row, at) for row in result]


    async def flags_near_path(
        self,
        path: Sequence[tuple[float, float]],
        radius_m: int,
        at: datetime,
    ) -> list[RiskFlag]:
        """
        Live flags within `radius_m` of the route, **highest current severity first**.

        This is defect 8. What it replaces in `route_service` was
        `select(CrimeReport)` with no spatial predicate at all -- every row in the table,
        pulled into Python, then a nested loop over every path point. The fix is not "a
        tighter Python loop", it is letting PostGIS and the GiST index answer the
        question they exist for.

        `ST_MakeLine` over the path, cast to `geography`, one `ST_DWithin`. On
        `geography` that is metres on a sphere, so `radius_m` means what it says at
        Dhaka's latitude; the same query on `geometry` would compare degrees and be wrong
        by a factor that changes as you move north.

        **Ordered by `severity_0`, not by distance** -- deliberately unlike `flags_near`.
        A caller asking about a corridor wants to know *what is worth knowing about this
        route*, and the worst thing on it matters more than the nearest thing. When
        `MAX_FLAGS_PER_READ` truncates, that is the ordering that keeps an explanation
        honest. Final ordering is by `severity_now` in Python, after decay -- see
        `flags_in_bbox` for why decay cannot be in the SQL.

        The path is thinned first (`simplify_for_corridor`): an OSRM `overview=full`
        geometry is several hundred points for a Dhaka crossing, and a LINESTRING that
        long makes the index work harder for no gain.
        """
        simplified = simplify_for_corridor(path)
        if len(simplified) < 2:
            # No corridor to ask about. This early return is not cosmetic: ST_MakeLine of
            # a single point returns NULL, ST_DWithin against NULL is NULL, every flag
            # would fail the predicate, and the route would score as perfectly safe. The
            # difference between "no flags" and "the question was malformed" matters when
            # the answer is used to tell someone a road is clear.
            return []

        # WKT rather than a bound array: asyncpg cannot adapt a list of tuples to a
        # PostGIS type, and the literal is built from floats already validated as
        # coordinates by the request schema, so there is no injection surface.
        line_wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in simplified) + ")"

        statement = text(
            f"""
            SELECT {_FLAG_COLUMNS}
            FROM public.risk_flags
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
                "limit": MAX_FLAGS_PER_READ,
            },
        )
        flags = [_row_to_flag(row, at) for row in result]
        flags.sort(key=lambda flag: flag.severity_now, reverse=True)
        return flags

    async def flags_near(
        self, lat: float, lon: float, radius_m: int, at: datetime
    ) -> list[RiskFlag]:
        """
        Live flags within `radius_m` metres of a point, nearest first.

        `ST_DWithin` on `geography` measures in metres on a sphere, which is why
        the column is `geography` and not `geometry` — the same query against
        `geometry` would compare degrees and be wrong by a factor that varies with
        latitude.
        """
        statement = text(
            f"""
            SELECT {_FLAG_COLUMNS}
            FROM public.risk_flags
            WHERE {_LIVE_PREDICATE}
              AND {POSTGIS_SCHEMA}.ST_DWithin(
                      location,
                      {POSTGIS_SCHEMA}.ST_SetSRID(
                          {POSTGIS_SCHEMA}.ST_MakePoint(:lon, :lat), 4326
                      )::{POSTGIS_SCHEMA}.geography,
                      :radius_m
                  )
            ORDER BY {POSTGIS_SCHEMA}.ST_Distance(
                         location,
                         {POSTGIS_SCHEMA}.ST_SetSRID(
                             {POSTGIS_SCHEMA}.ST_MakePoint(:lon, :lat), 4326
                         )::{POSTGIS_SCHEMA}.geography
                     ) ASC
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            statement,
            {
                "at": at,
                "lat": lat,
                "lon": lon,
                "radius_m": radius_m,
                "limit": MAX_FLAGS_PER_READ,
            },
        )
        return [_row_to_flag(row, at) for row in result]
