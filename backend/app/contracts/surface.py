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
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

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
