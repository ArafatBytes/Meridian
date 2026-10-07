"""
`SeededRiskSurface` — the fixture behind the `RiskSurface` protocol. No database.

This is the offline demo path. With `RISK_SURFACE_IMPL=seeded` the map works with
Postgres stopped, the network down and the LLM key revoked, which is what D10's
failure drills rehearse and what makes the venue's wifi a non-event rather than a
risk. It is the reason the fixture is called the most valuable artifact in the track.

It satisfies exactly the same protocol as `DbRiskSurface` and returns the same
`RiskFlag` shape, so the endpoint cannot tell them apart. A test asserts both satisfy
the protocol; that is the seam working.

What it has to do that the database normally does
-------------------------------------------------
Three things, and each is a mirror with a named authority:

* **`flag_id`** — a UUID. Generated deterministically from `event_key` with `uuid5`,
  so a flag keeps the same id across process restarts. A random id per load would
  change React's keys on every reload and make the map remount pins for no reason.
* **`expires_at`** — derived. `decay.expires_at_for()` mirrors the SQL trigger; see
  that function for why the duplication is unavoidable here.
* **spatial filtering** — `ST_Intersects` and `ST_DWithin` become a box test and a
  haversine. At 212 flags that is microseconds, and bringing in `shapely` to do it
  would be a dependency for arithmetic that fits in ten lines.

One load instant for the whole process
--------------------------------------
Fixture offsets are relative, so they have to be resolved against *something*. That
something is the moment the fixture is first loaded, held for the life of the
process. Resolving against `datetime.now()` per request would mean a flag's
`observed_at` moved forward between two requests, so nothing would ever appear to
decay — and the decay demo is the point of the sprint.

The practical consequence, worth knowing before a rehearsal: **restarting the backend
resets the surface to "all flags fresh".** That is usually what you want on stage, and
it is why `RISK_SURFACE_IMPL=seeded` is also the safest thing to be running if a
rehearsal has been going for hours.
"""

import math
from datetime import UTC, datetime
from typing import Any, Final
from uuid import NAMESPACE_URL, UUID, uuid5

from app.contracts.risk import IncidentKind, RiskFlag, SourceRef, TimeProfile
from app.scoring.decay import expires_at_for, is_live, severity_at
from app.scoring.fixture import fixture_rows

MAX_FLAGS_PER_READ: Final[int] = 500
"""Mirrors `surface_db.MAX_FLAGS_PER_READ`, so the two surfaces truncate alike."""

_FLAG_ID_NAMESPACE: Final[UUID] = uuid5(NAMESPACE_URL, "https://meridian.app/risk_flags/seed")
"""
A fixed namespace for `uuid5(namespace, event_key)`.

Derived from a URL rather than typed as a literal so it is reproducible by reading
this line, and stable forever.
"""

EARTH_RADIUS_M: Final[float] = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance in metres.

    The same measure `ST_DWithin` on a `geography` column uses, which is why the
    column is `geography` and not `geometry` — a planar comparison would be in degrees
    and wrong by a factor that varies with latitude.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class _SeededFlag:
    """
    One fixture row, with its derived fields resolved once.

    A small class rather than a dict because `flags_in_bbox` touches every field on
    every read and the attribute access documents itself. Not a `RiskFlag`, because a
    `RiskFlag` carries `severity_now`, which depends on the instant being asked about
    and so cannot be computed at load time.
    """

    __slots__ = (
        "flag_id",
        "event_key",
        "kind",
        "status",
        "lat",
        "lon",
        "radius_m",
        "severity_0",
        "half_life_hours",
        "observed_at",
        "expires_at",
        "valid_from",
        "valid_to",
        "source_count",
        "sources",
        "mobility_statement",
        "time_profile",
    )

    def __init__(self, row: dict[str, Any]) -> None:
        self.flag_id = uuid5(_FLAG_ID_NAMESPACE, row["event_key"])
        self.event_key: str = row["event_key"]
        self.kind = IncidentKind(row["kind"])
        self.status: str = row["status"]
        self.lat: float = row["lat"]
        self.lon: float = row["lon"]
        self.radius_m: int = row["radius_m"]
        self.severity_0: float = row["severity_0"]
        self.half_life_hours: float = row["half_life_hours"]
        self.observed_at: datetime = row["observed_at"]
        self.valid_from: datetime | None = row["valid_from"]
        self.valid_to: datetime | None = row["valid_to"]
        self.source_count: int = row["source_count"]
        self.sources = [SourceRef(**source) for source in row["sources"]]
        self.mobility_statement: str = row["mobility_statement"]
        # The fixture never sets a per-flag profile; the kind default is applied by
        # `decay.severity_at` when this is None, which is every flag today.
        self.time_profile: TimeProfile | None = None
        self.expires_at = expires_at_for(
            severity_0=self.severity_0,
            half_life_hours=self.half_life_hours,
            observed_at=self.observed_at,
            valid_to=self.valid_to,
        )

    def to_contract(self, at: datetime) -> RiskFlag:
        """This flag as the client sees it at the instant `at`."""
        return RiskFlag(
            flag_id=self.flag_id,
            event_key=self.event_key,
            kind=self.kind,
            status=self.status,  # type: ignore[arg-type]  # validated by check_rows
            lat=self.lat,
            lon=self.lon,
            radius_m=self.radius_m,
            severity_0=self.severity_0,
            severity_now=severity_at(
                severity_0=self.severity_0,
                half_life_hours=self.half_life_hours,
                observed_at=self.observed_at,
                at=at,
                kind=self.kind,
                valid_from=self.valid_from,
                time_profile=self.time_profile,
            ),
            half_life_hours=self.half_life_hours,
            observed_at=self.observed_at,
            expires_at=self.expires_at,
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            source_count=self.source_count,
            sources=self.sources,
            mobility_statement=self.mobility_statement,
            time_profile=self.time_profile,
        )


_CACHE: list[_SeededFlag] | None = None
_LOADED_AT: datetime | None = None


def loaded_flags() -> list[_SeededFlag]:
    """
    The fixture, loaded once per process. See the module docstring on the load instant.
    """
    global _CACHE, _LOADED_AT
    if _CACHE is None:
        _LOADED_AT = datetime.now(UTC)
        _CACHE = [_SeededFlag(row) for row in fixture_rows(_LOADED_AT)]
    return _CACHE


def loaded_at() -> datetime | None:
    """When the fixture was resolved. `None` before the first read. For diagnostics."""
    return _LOADED_AT


def reset_cache() -> None:
    """
    Drop the cache so the next read re-resolves the fixture against a new instant.

    For tests, and for a rehearsal that wants every flag fresh without restarting the
    process. Not reachable over HTTP: a request that could rewind the surface is a
    request that could rewind it mid-demo.
    """
    global _CACHE, _LOADED_AT
    _CACHE = None
    _LOADED_AT = None


class SeededRiskSurface:
    """
    Serves `data/fixtures/risk_flags.json`. Satisfies `app.contracts.surface.RiskSurface`.

    Takes no session. The constructor accepts and ignores one so that the factory in
    `app/scoring/__init__.py` can build either surface the same way; a surface that
    needed a different call shape would push the branch out to every caller, which is
    the opposite of what the protocol is for.
    """

    def __init__(self, session: object | None = None) -> None:
        self._session = session

    def _live(self, at: datetime) -> list[_SeededFlag]:
        """
        The Python statement of `surface_db._LIVE_PREDICATE`.

        Status first, then the instants. The status test is here rather than in
        `decay.is_live` because it is about the flag's lifecycle and not about time.
        """
        return [
            flag
            for flag in loaded_flags()
            if flag.status in ("unconfirmed", "confirmed")
            and is_live(at=at, expires_at=flag.expires_at, valid_to=flag.valid_to)
        ]

    async def flags_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        at: datetime,
    ) -> list[RiskFlag]:
        """
        Live flags inside a bounding box, highest severity first.

        Ordered by `severity_now` rather than `severity_0`: when the read is truncated
        at `MAX_FLAGS_PER_READ`, what should survive is what matters *now*, and sorting
        on the stored value would keep a long-decayed severe flag over a fresh moderate
        one. `DbRiskSurface` orders on `severity_0` in SQL for the same reason it has to
        — the decay is not expressible in that ORDER BY without recomputing it per row —
        and at 212 flags neither read is anywhere near the limit, so the two agree in
        practice. Noted rather than hidden.

        `async` with nothing awaited, because the protocol is async and the database
        implementation genuinely is. The alternative is two protocols.
        """
        flags = [
            flag
            for flag in self._live(at)
            if min_lat <= flag.lat <= max_lat and min_lon <= flag.lon <= max_lon
        ]
        contracts = [flag.to_contract(at) for flag in flags]
        contracts.sort(key=lambda flag: flag.severity_now, reverse=True)
        return contracts[:MAX_FLAGS_PER_READ]

    async def flags_near(
        self, lat: float, lon: float, radius_m: int, at: datetime
    ) -> list[RiskFlag]:
        """Live flags within `radius_m` metres of a point, nearest first."""
        within = [
            (_haversine_m(lat, lon, flag.lat, flag.lon), flag) for flag in self._live(at)
        ]
        within = [(distance, flag) for distance, flag in within if distance <= radius_m]
        within.sort(key=lambda pair: pair[0])
        return [flag.to_contract(at) for _, flag in within[:MAX_FLAGS_PER_READ]]
