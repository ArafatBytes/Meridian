"""
The risk surface seam — IMPLEMENTATION_PLAN.md §6.2.

Everything that consumes risk talks to a `RiskSurface` and never to a table. That
is what lets D02 add a fixture-backed surface for the offline demo path, and D06
build route scoring, without either touching the other's code or the API layer.

Implementations, and when they land:

| Implementation         | Source                          | Lands |
|------------------------|---------------------------------|-------|
| `DbRiskSurface`        | the `risk_flags` table          | D01 |
| `SeededRiskSurface`    | `data/fixtures/risk_flags.json` | D02 |
| `LegacyRegionalSurface`| `scripts/crime_risk_model.json` | Track B |

Selection becomes one settings value, `RISK_SURFACE_IMPL`, in D02 — when there is
a second implementation to select between. D01 has one, and the endpoint names it
directly rather than dispatching through a factory that can only return one thing.

**This protocol only declares what something implements today.** The scoring
methods the long plan shows here (`score_point`, `score_path`, and the `PointRisk`
/ `PathRisk` shapes) arrive with the Risk Scoring Engine in D02 and route scoring
in D06. Declaring them now would mean either dead implementations or a protocol
nothing satisfies, and both are worse than adding two methods later.

D06 added `flags_near_path`, and S12 pre-authorised it: *"verify `seeded` and
`legacy` both work with zero changes in `routing/` -- if either needs one, fix the
contract now."* It needed one. Scoring a route against `flags_in_bbox` would have
worked and been quietly wrong: a route across Dhaka has a bounding box covering most
of the city, so it would score against flags kilometres from any road on it. The
corridor is the question, so the corridor is the query.

What did **not** happen is a `score_path` method. Scoring is a policy decision --
which weights, whether `confidence` damps severity -- and policy belongs in
`app/routing/scorer.py` where it can be read in one place. A surface answers *what is
near this path*; it does not get an opinion about what that is worth.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.contracts.community import CommunityCluster
from app.contracts.risk import RiskFlag


@runtime_checkable
class RiskSurface(Protocol):
    """
    What every risk source must be able to answer.

    `runtime_checkable` so a test can assert an implementation satisfies the
    protocol without standing up a database. Note that this checks method *names*
    at runtime only; `mypy --strict` is what checks the signatures, which is why
    the strict override on `app.scoring.*` in pyproject.toml matters.

    Every method takes an explicit instant. Nothing in a surface may read the wall
    clock: decay, time-of-day modulation and D09's forward-looking view all depend
    on the caller choosing the moment.
    """

    async def flags_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        at: datetime,
    ) -> list[RiskFlag]: ...

    async def flags_near(
        self, lat: float, lon: float, radius_m: int, at: datetime
    ) -> list[RiskFlag]: ...

    async def flags_near_path(
        self,
        path: Sequence[tuple[float, float]],
        radius_m: int,
        at: datetime,
    ) -> list[RiskFlag]:
        """
        Live flags within `radius_m` of a polyline, highest current severity first.

        `path` is `(lat, lon)` pairs in travel order -- the same order the client
        draws them, not PostGIS's `(lon, lat)`. Each implementation converts; callers
        should not have to remember which convention they are in.

        **D06, defect 8.** The method route scoring needs, and the reason it is on the
        protocol rather than inside `DbRiskSurface`: `routing/` must work unchanged on
        every surface, and a bounding box is not an acceptable substitute. A 12 km
        route across Dhaka has a bounding box containing most of the city's flags,
        almost none of which are on it.

        A path of fewer than two points returns `[]`: there is no corridor to ask
        about, and a single point is what `flags_near` is for.
        """
        ...


@runtime_checkable
class ClusterSurface(Protocol):
    """
    What a source of community report clusters must answer. B13.

    A second, smaller protocol rather than two more methods on `RiskSurface`, and
    the reason is the one `app/scoring/clusters.py` opens with: `RiskSurface`'s
    methods return `RiskFlag`, and a cluster of user reports cannot become one
    without inventing an `IncidentKind` it does not have and a mobility statement
    `app/policy/framing.py` will not let it produce.

    Keeping them apart is also what lets a consumer be explicit about which claim it
    is weighing. `app/routing/scorer.py` takes one of each and applies different
    weights, because two strangers agreeing is not what two newspapers agreeing is.

    One implementation today -- `app.scoring.clusters.DbClusterSurface`. There is no
    seeded counterpart on purpose: a fixture cluster would be a fabricated claim
    that people reported incidents at a named corner, so the offline path serves
    none. Hence every consumer accepts `ClusterSurface | None` and behaves
    correctly with `None`, which is also what keeps `RISK_SURFACE_IMPL=seeded`
    working with no branch in the routing code.

    Every method takes an explicit instant, for the reason `RiskSurface` does:
    nothing in a surface may read the wall clock.
    """

    async def clusters_near_path(
        self,
        path: Sequence[tuple[float, float]],
        radius_m: int,
        at: datetime,
    ) -> list[CommunityCluster]:
        """
        Live clusters within `radius_m` of a polyline, highest current severity first.

        `path` is `(lat, lon)` pairs in travel order, matching `flags_near_path` --
        callers should not have to remember which convention they are in. Fewer than
        two points returns `[]`: there is no corridor to ask about.
        """
        ...

    async def clusters_in_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        at: datetime,
    ) -> list[CommunityCluster]: ...
