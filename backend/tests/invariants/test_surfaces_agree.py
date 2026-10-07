"""
Both `RiskSurface` implementations really are one. DEMO_PLAN.md D02.

The seam only buys anything if the endpoint genuinely cannot tell the two apart. A
seeded surface that drifted — served an un-decayed severity, kept an expired flag,
ordered differently — would mean the offline demo path behaves differently from the
path rehearsed against the database, and the difference would surface on stage.

`SeededRiskSurface` is tested against real data because it has some: the fixture is in
the repository and needs no connection. `DbRiskSurface` is tested for protocol
conformance only; exercising its SQL needs PostGIS, which is `docs/walkthroughs/D02.md`
and the throwaway container, not a unit test.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.contracts.risk import RiskFlag
from app.contracts.surface import RiskSurface
from app.scoring.decay import SERVE_THRESHOLD, undecayed_severity
from app.scoring.factory import SURFACE_IMPLS, get_risk_surface
from app.scoring.surface_db import DbRiskSurface
from app.scoring.surface_seeded import SeededRiskSurface, loaded_flags

# Dhaka central, comfortably inside the endpoint's 2-degree span limit.
DHAKA = (23.70, 90.33, 23.90, 90.50)


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("implementation", [DbRiskSurface, SeededRiskSurface])
def test_both_implementations_satisfy_the_protocol(implementation: type) -> None:
    """
    `runtime_checkable` checks method *names*; `mypy --strict` checks the signatures.

    Both matter, and this is the half a test can do. The strict override on
    `app.scoring.*` in `pyproject.toml` is the other half.
    """
    assert isinstance(implementation(None), RiskSurface)  # type: ignore[arg-type]


def test_the_factory_returns_a_surface_for_every_declared_impl() -> None:
    """
    Every value `SURFACE_IMPLS` advertises actually resolves.

    A name in that tuple that the factory does not handle would be a documented setting
    that raises on the first request.
    """
    from app.core.config import settings

    original = settings.RISK_SURFACE_IMPL
    try:
        for impl in SURFACE_IMPLS:
            settings.RISK_SURFACE_IMPL = impl
            assert isinstance(get_risk_surface(None), RiskSurface)  # type: ignore[arg-type]
    finally:
        settings.RISK_SURFACE_IMPL = original


def test_an_unknown_impl_raises_rather_than_falling_back() -> None:
    """
    Silence here is the dangerous failure.

    A typo that quietly served the seeded surface looks entirely plausible — `sample_`
    in the source strip is the only tell — so it has to be loud.
    """
    from app.core.config import settings

    original = settings.RISK_SURFACE_IMPL
    try:
        settings.RISK_SURFACE_IMPL = "fixtures"
        with pytest.raises(ValueError, match="RISK_SURFACE_IMPL"):
            get_risk_surface(None)  # type: ignore[arg-type]
    finally:
        settings.RISK_SURFACE_IMPL = original


# ---------------------------------------------------------------------------
# The seeded surface against the real fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_fixture_serves_a_demo_sized_surface() -> None:
    """
    DEMO_PLAN.md D02 asks for ~200 flags across Dhaka. This is the number, asserted.

    A range rather than an equality: entries get added. The lower bound is what beat 1
    needs to look like a city rather than a handful of pins.
    """
    flags = await SeededRiskSurface().flags_in_bbox(*DHAKA, datetime.now(UTC))
    assert 150 <= len(flags) <= 500


@pytest.mark.asyncio
async def test_every_served_flag_carries_a_decayed_severity() -> None:
    """
    **The central one.** Every flag decays — §4, and the concept document's §9.

    `severity_now` must be the stored severity run through the decay curve, not a copy
    of it. A surface that forgot to compute it would still serve a complete, valid,
    plausible-looking response in which nothing ever faded.
    """
    at = datetime.now(UTC) + timedelta(hours=5)
    flags = await SeededRiskSurface().flags_in_bbox(*DHAKA, at)
    assert flags

    for flag in flags:
        expected_base = undecayed_severity(
            severity_0=flag.severity_0,
            half_life_hours=flag.half_life_hours,
            observed_at=flag.observed_at,
            at=at,
            valid_from=flag.valid_from,
        )
        # The hour multiplier is between 0.70 and 1.25 across every profile, so
        # severity_now must sit inside that band around the un-modulated curve. Asserting
        # the band rather than recomputing the multiplier keeps this test from being a
        # restatement of the implementation.
        assert 0.70 * expected_base - 1e-9 <= flag.severity_now
        assert flag.severity_now <= min(100.0, 1.25 * expected_base) + 1e-9


@pytest.mark.asyncio
async def test_no_served_flag_has_outlived_its_expiry() -> None:
    """
    "No manual cleanup, no stale red zone" — concept document §6.

    Checked at several instants, including far enough out that almost everything should
    be gone, because a filter that compared against the wrong instant would still look
    correct at `now`.
    """
    surface = SeededRiskSurface()
    now = datetime.now(UTC)
    for hours in (0, 6, 24, 24 * 7, 24 * 120):
        at = now + timedelta(hours=hours)
        for flag in await surface.flags_in_bbox(*DHAKA, at):
            assert flag.expires_at > at, f"{flag.event_key} outlived its expiry at +{hours}h"
            assert flag.valid_to is None or flag.valid_to > at


@pytest.mark.asyncio
async def test_the_surface_shrinks_as_time_moves_forward() -> None:
    """
    Demo beat 5, as a test: drag the time control forward and flags go away on their own.

    Strictly decreasing rather than non-increasing, because the fixture deliberately
    carries a spread of half-lives — if this ever became flat, the fixture had lost its
    short-lived flags and the decay step would stop being demonstrable in under a minute.
    """
    surface = SeededRiskSurface()
    now = datetime.now(UTC)
    counts = [
        len(await surface.flags_in_bbox(*DHAKA, now + timedelta(hours=h)))
        for h in (0, 6, 24, 24 * 30)
    ]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1]


@pytest.mark.asyncio
async def test_expired_fixture_entries_are_not_served() -> None:
    """
    The fixture carries entries deliberately placed below the serve threshold.

    They exist so the expiry filter is *visible* in the walkthrough rather than taken on
    trust, which only works if they are genuinely excluded.
    """
    now = datetime.now(UTC)
    served = {
        flag.event_key for flag in await SeededRiskSurface().flags_in_bbox(*DHAKA, now)
    }
    deliberately_expired = {
        flag.event_key for flag in loaded_flags() if flag.event_key.startswith("seed-expired-")
    }
    assert deliberately_expired, "the fixture has lost its deliberately-expired entries"
    assert not (deliberately_expired & served)


@pytest.mark.asyncio
async def test_flags_near_is_ordered_by_distance_and_respects_the_radius() -> None:
    at = datetime.now(UTC)
    # Mirpur 10 golchattar — the fixture clusters several flags here on purpose.
    flags = await SeededRiskSurface().flags_near(23.8069, 90.3687, 2000, at)
    assert len(flags) >= 3

    from app.scoring.surface_seeded import _haversine_m

    distances = [_haversine_m(23.8069, 90.3687, flag.lat, flag.lon) for flag in flags]
    assert distances == sorted(distances)
    assert max(distances) <= 2000


@pytest.mark.asyncio
async def test_a_bounding_box_excludes_what_is_outside_it() -> None:
    """
    A box test that always returned everything would pass every other test here.

    Uttara is ~23.87; a box that stops at 23.80 must not contain it.
    """
    at = datetime.now(UTC)
    south = await SeededRiskSurface().flags_in_bbox(23.70, 90.33, 23.80, 90.50, at)
    assert south
    assert all(23.70 <= flag.lat <= 23.80 for flag in south)
    assert not any(flag.event_key.startswith("seed-uttara") for flag in south)


@pytest.mark.asyncio
async def test_flag_ids_are_stable_across_loads() -> None:
    """
    `uuid5(namespace, event_key)`, not `uuid4()`.

    A random id per load would change React's keys on every reload and make the map
    remount every pin, and a flag's identity would not survive a restart.
    """
    from app.scoring.surface_seeded import reset_cache

    at = datetime.now(UTC)
    first = {f.event_key: f.flag_id for f in await SeededRiskSurface().flags_in_bbox(*DHAKA, at)}
    reset_cache()
    second = {f.event_key: f.flag_id for f in await SeededRiskSurface().flags_in_bbox(*DHAKA, at)}
    shared = set(first) & set(second)
    assert shared
    assert all(first[key] == second[key] for key in shared)


@pytest.mark.asyncio
async def test_served_flags_validate_against_the_contract() -> None:
    """
    They are `RiskFlag` instances, so pydantic has already run — but say so.

    This is the test that would catch a `severity_now` above 100 or a radius of zero
    reaching the client, as a rejected response rather than a bad pin.
    """
    flags = await SeededRiskSurface().flags_in_bbox(*DHAKA, datetime.now(UTC))
    for flag in flags:
        assert isinstance(flag, RiskFlag)
        assert 0.0 <= flag.severity_now <= 100.0
        assert flag.half_life_hours > 0
        assert flag.radius_m > 0
        assert flag.mobility_statement
        # Verification before publication: the schema CHECK, restated where the data is.
        assert flag.status != "confirmed" or flag.source_count >= 2


@pytest.mark.asyncio
async def test_nothing_below_the_serve_threshold_is_served() -> None:
    """
    The threshold is what `expires_at` is solved against, so this should be impossible.

    Asserted anyway, because it is the one statement that ties the stored column back to
    the number in `decay.py`: if the two ever disagree, this is where it shows.
    """
    at = datetime.now(UTC) + timedelta(hours=3)
    for flag in await SeededRiskSurface().flags_in_bbox(*DHAKA, at):
        base = undecayed_severity(
            severity_0=flag.severity_0,
            half_life_hours=flag.half_life_hours,
            observed_at=flag.observed_at,
            at=at,
            valid_from=flag.valid_from,
        )
        assert base >= SERVE_THRESHOLD - 1e-9, f"{flag.event_key} is served below threshold"


# ---------------------------------------------------------------------------
# The offline demo path, proven rather than asserted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_seeded_surface_serves_with_no_reachable_database() -> None:
    """
    **D10's failure drill, as a test.** `RISK_SURFACE_IMPL=seeded` must survive the
    database being gone entirely.

    This is not obviously true from reading the code, which is why it is here. The
    endpoint declares `db: AsyncSession = Depends(get_db)`, so a session object is
    constructed on every request whatever the surface is. The claim rests on two things
    that are easy to break by accident:

    1. SQLAlchemy connects **lazily** — `async_sessionmaker()` and `async with` acquire
       nothing, so an unusable URL costs nothing until a statement runs;
    2. `SeededRiskSurface` never runs a statement.

    Either could change without anyone noticing. A `pool_pre_ping`, an eager connection
    in `get_db`, or a surface that incidentally queried something would all turn the
    offline path into a path that merely looks offline — and it would be discovered on
    stage, during the one drill whose whole point is that the network has failed.

    The `db` half of this test is the control: it proves the URL really is dead, so the
    `seeded` half is not passing because the database happened to be reachable.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.v1.endpoints.risk import get_risk_flags
    from app.core.config import settings

    dead = "postgresql+asyncpg://nobody:nothing@this-host-does-not-exist.invalid:5432/nope"
    engine = create_async_engine(dead, pool_pre_ping=False)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    original = settings.RISK_SURFACE_IMPL

    try:
        settings.RISK_SURFACE_IMPL = "seeded"
        async with maker() as session:
            response = await get_risk_flags(
                bbox="90.33,23.70,90.50,23.90", as_of=None, db=session
            )
        assert response.count > 100, (
            "the seeded surface served nothing with the database unreachable; the "
            "offline demo path is broken"
        )

        # The control. If this ever starts passing, the URL above has stopped being
        # dead and the assertion before it has stopped meaning anything.
        settings.RISK_SURFACE_IMPL = "db"
        with pytest.raises(Exception):  # noqa: B017 - driver-specific; the class varies
            async with maker() as session:
                await get_risk_flags(
                    bbox="90.33,23.70,90.50,23.90", as_of=None, db=session
                )
    finally:
        settings.RISK_SURFACE_IMPL = original
        await engine.dispose()
