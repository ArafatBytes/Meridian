"""
Choosing a risk surface. The only place that does.

Separate from `app/scoring/__init__.py` on purpose, and the reason is worth stating
because it was found the hard way. The factory needs `app.core.config.settings`, and
`Settings` has two required fields with no defaults — `DATABASE_URL` and
`JWT_SECRET_KEY` — so importing it raises a `ValidationError` unless a `.env` is
discoverable from the current working directory.

With this function living in the package's `__init__`, **every** import from
`app.scoring` paid that cost. `scripts/seed_risk_flags.py --sql` imports
`app.scoring.fixture` to turn a JSON file into SQL text; it touches no database and
needs no credentials, yet it crashed when run from the repository root rather than from
`backend/`. A tool whose job is to hand you paste-ready SQL failing on a missing
database URL is the kind of coupling that is invisible until it is in the way.

So: `fixture.py`, `decay.py`, `kinds.py` and `chronic.py` are importable with no
configuration at all, and only the thing that genuinely needs settings imports them.
"""

from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.surface import RiskSurface
from app.core.config import settings
from app.scoring.surface_db import DbRiskSurface
from app.scoring.surface_seeded import SeededRiskSurface

SURFACE_IMPLS: Final[tuple[str, ...]] = ("db", "seeded")


def get_risk_surface(session: AsyncSession) -> RiskSurface:
    """
    The risk surface this process serves, per `RISK_SURFACE_IMPL`.

    `db` (the default) reads `risk_flags`. `seeded` reads the fixture and never touches
    the database — the offline demo path, and what D10's failure drills switch to when
    the venue network or Postgres goes down mid-script.

    The return type is the protocol, not either class. That is the whole point of the
    seam: the endpoint holds a `RiskSurface` and cannot tell which one it got, so
    switching implementations is an environment variable rather than a code change.

    An unknown value raises at the first request rather than falling back silently. A
    typo in `.env` that quietly served the wrong surface is the kind of thing that is
    found on stage: the seeded surface looks completely plausible, and `sample_` in the
    source strip is the only tell.
    """
    impl = settings.RISK_SURFACE_IMPL.strip().lower()
    if impl == "db":
        return DbRiskSurface(session)
    if impl == "seeded":
        return SeededRiskSurface(session)
    raise ValueError(
        f"RISK_SURFACE_IMPL={settings.RISK_SURFACE_IMPL!r} is not one of {SURFACE_IMPLS}"
    )
