"""
Invariant: **every table is classified, and nothing outlives its window.** B14.

Concept document §9 makes one testable privacy promise: *"Location history is
retained only as long as operationally necessary."* HTTPS and JWT, the clause's
other two halves, were already provable from the transport and the auth
middleware. This one was a sentence with nothing behind it — no table declared a
window, nothing deleted anything, and no test could fail.

**The important test here is not the window, it is the tripwire.** `PURGES` was
written on 2026-10-15 against the live schema, and the single most sensitive table
in it — `journeys`, holding a per-user origin and destination, which is exactly
what §9 names — is one **this repository has no code for**. Applied by hand as
ledger version 20261014150000, no committed migration, no implementation on any
branch, and accumulating rows that afternoon. Nobody writing a retention sweep
from memory would have covered it.

So the load-bearing assertion is `test_every_table_in_the_database_is_classified`:
a new table fails it until somebody decides what it holds. The windows are the
easy part and most of them are still `PROPOSED`.

Layer 3 is marked `integration` and skips without a database, for the same reason
`test_single_source_never_confirmed` does: a developer with no Supabase
credentials should see the declarative layers pass, not a connection error dressed
as a privacy violation.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest

from app.privacy.retention import (
    PURGES,
    Basis,
    Disposal,
    proposed_windows,
    retention_for,
    tables_with_windows,
)

pytestmark = pytest.mark.invariant

# Tables that exist to serve the framework rather than the product. Postgres
# extensions create these; they are not ours to classify.
_NOT_OURS = frozenset({"spatial_ref_sys", "geography_columns", "geometry_columns"})

# Resolved once at import. The async tests need it too, and `Path.resolve()` inside
# a coroutine is a blocking filesystem call (ruff ASYNC240).
_BACKEND: Final = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 1. The registry is internally coherent
# ---------------------------------------------------------------------------


def test_every_rule_is_well_formed() -> None:
    """
    `Retention.__post_init__` enforces this on construction, so importing the module
    is most of the test. This states the guarantee out loud rather than relying on a
    dataclass to fail at import time, which is a confusing place for a policy error
    to surface.
    """
    for rule in PURGES:
        assert rule.table, "a rule with no table name"
        assert rule.holds.strip(), f"{rule.table}: must say what it holds"
        assert rule.why.strip(), f"{rule.table}: must say why"
        if rule.disposal is Disposal.DELETE:
            assert rule.window and rule.window > timedelta(0), rule.table
            assert rule.dated_by, rule.table
            assert rule.basis, rule.table
        else:
            assert rule.window is None, f"{rule.table}: KEEP must carry no window"


def test_no_table_is_classified_twice() -> None:
    """Two rules for one table means one of them is silently dead."""
    seen = [rule.table for rule in PURGES]
    duplicates = {name for name in seen if seen.count(name) > 1}
    assert duplicates == set(), f"classified more than once: {sorted(duplicates)}"


def test_a_keep_decision_has_to_argue_for_itself() -> None:
    """
    `KEEP` is a decision, not an absence, and the distinction only survives if the
    reasoning is there. A one-word `why` would make the registry indistinguishable
    from a list of tables nobody got to.
    """
    thin = [
        rule.table
        for rule in PURGES
        if rule.disposal is Disposal.KEEP and len(rule.why.split()) < 8
    ]
    assert thin == [], f"KEEP with no argument: {thin}"


def test_the_location_tables_carry_the_shortest_windows() -> None:
    """
    §9 is specifically about location history, so the tables it names cannot be the
    laxest in the registry. `user_locations` is raw pings and `journeys` is
    origin-destination history; both must expire sooner than operational telemetry.
    """
    windows = {rule.table: rule.window for rule in tables_with_windows()}
    assert windows["user_locations"] < windows["agent_runs"], (
        "raw position pings are kept longer than agent telemetry, which inverts §9"
    )
    assert windows["journeys"] <= windows["agent_runs"], (
        "movement history is kept longer than agent telemetry, which inverts §9"
    )


# ---------------------------------------------------------------------------
# 2. The tripwire — a new table must be classified
# ---------------------------------------------------------------------------
#
# Everything below needs the live schema, which means two traps worth naming,
# because the first draft of this file fell into both.
#
# **The pool outlives the event loop it was built on.** `pyproject.toml` sets
# `asyncio_mode = "auto"`, so pytest-asyncio gives each async test its own loop,
# while `app.core.database.engine` is a module-level singleton whose pooled
# connections belong to whichever loop first used them. The first integration
# test here passed and the next two failed with `RuntimeError` and `DBAPIError` —
# not because the database was unreachable, but because the connection was
# attached to a loop that no longer existed. `engine.dispose(close=False)` before
# use fixes it -- `close=False` matters, because a plain dispose tries to shut the
# old loop's connections and raises `RuntimeError: Event loop is closed` doing it;
# the flag swaps the pool and leaves the dead connections to be collected. This
# it. `test_single_source_never_confirmed` never hit this because it has exactly
# one integration test.
#
# **A broad `except` around a query turns a bug into a skip.** The first draft
# wrapped the whole query in `except Exception: pytest.skip("database
# unreachable")`, which is how the loop problem above spent a while looking like a
# missing database. So the skip now covers only *connecting*; a query that fails
# after a successful connect is a real failure and is allowed to be one.


async def _live_tables() -> set[str]:
    """
    Base table names in `public`, or skip if there is genuinely no database.

    Disposes the pool first — see the note above. Only the connect is guarded.
    """
    try:
        from app.core.database import AsyncSessionLocal, engine
    except Exception as exc:  # pragma: no cover - import-time config failure
        pytest.skip(f"no database configured: {exc}")

    from sqlalchemy import text as sql

    await engine.dispose(close=False)
    try:
        connection = AsyncSessionLocal()
        await connection.connection()
    except Exception as exc:
        pytest.skip(f"database unreachable: {type(exc).__name__}: {exc}")

    async with connection as db:
        rows = (
            await db.execute(
                sql(
                    "select table_name from information_schema.tables "
                    "where table_schema = 'public' and table_type = 'BASE TABLE'"
                )
            )
        ).scalars().all()
    return {str(name) for name in rows}


@pytest.mark.integration
async def test_every_table_in_the_database_is_classified() -> None:
    """
    **The test this module exists for.**

    If you are here because it failed, a table was added and nobody said what it
    holds. That is exactly how `journeys` came to hold movement history that no
    retention rule covered: applied by hand, no committed migration, no code in this
    repository, and found only because B14 read the live schema instead of the
    models.

    Add a `Retention` for it. `KEEP` is a perfectly good answer — it just has to be
    an answer, with a reason, in the same structure as a window.
    """
    live = await _live_tables() - _NOT_OURS
    unclassified = sorted(name for name in live if retention_for(name) is None)
    assert unclassified == [], (
        "tables in the database with no retention decision: "
        f"{unclassified}. Add a Retention to app/privacy/retention.py — KEEP is a "
        "valid answer, silence is not."
    )


@pytest.mark.integration
async def test_the_registry_does_not_describe_tables_that_do_not_exist() -> None:
    """
    The other direction, and a weaker failure: a rule for a dropped table is dead
    policy. It matters because a purge script iterating `PURGES` would either error
    or silently skip, and a registry that lists protections which cannot run reads
    as more coverage than it has.
    """
    live = await _live_tables()
    phantom = sorted(rule.table for rule in PURGES if rule.table not in live)
    assert phantom == [], f"retention rules for tables that no longer exist: {phantom}"


# ---------------------------------------------------------------------------
# 3. Nothing has outlived its window
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_no_row_is_older_than_its_declared_window() -> None:
    """
    The promise, measured against the rows that actually exist.

    **This is expected to fail until `scripts/purge_expired.py` has been run**, and
    that is the honest state of the project rather than a reason to weaken the test:
    the windows were declared on 2026-10-15 and nothing has ever deleted anything, so
    rows predating them are simply there. A failure names the table and the count.

    `PROPOSED` windows are reported but not asserted. A retention period nobody has
    signed off should not be able to turn the suite red — and it should not be able
    to delete anybody's data either, which is why the purge script refuses them too.
    """
    try:
        from app.core.database import AsyncSessionLocal, engine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database configured: {exc}")

    from datetime import UTC, datetime

    from sqlalchemy import text as sql

    now = datetime.now(UTC)
    overdue: list[str] = []
    advisory: list[str] = []

    await engine.dispose(close=False)  # see the note above section 2
    try:
        session = AsyncSessionLocal()
        await session.connection()
    except Exception as exc:
        pytest.skip(f"database unreachable: {type(exc).__name__}: {exc}")

    async with session as db:
        # Eight columns in this schema are `timestamp without time zone` --
        # crime_reports (3), sos_incidents (2), user_locations.timestamp and
        # users (2) -- while everything else is `timestamptz`. Comparing a naive
        # column against an aware cutoff makes asyncpg type the parameter naive
        # and fail with "can't subtract offset-naive and offset-aware datetimes".
        #
        # So the naive ones are interpreted as UTC, **explicitly**, rather than by
        # leaning on the session's TimeZone being UTC today. A retention window
        # that silently changed meaning with a server setting would be the wrong
        # kind of quiet. ⚠️ The real fix is a migration making the schema
        # consistent; until then this is where the assumption is written down.
        naive = {
            (row[0], row[1])
            for row in (
                await db.execute(
                    sql(
                        "select table_name, column_name from information_schema.columns "
                        "where table_schema = 'public' "
                        "and data_type = 'timestamp without time zone'"
                    )
                )
            ).all()
        }

        for rule in tables_with_windows():
            assert rule.window and rule.dated_by
            cutoff = now - rule.window
            column = rule.dated_by
            if (rule.table, column) in naive:
                column = f"({column} at time zone 'UTC')"
            count = (
                await db.execute(
                    sql(
                        f"select count(*) from public.{rule.table} "  # noqa: S608
                        f"where {rule.dated_by} is not null and {column} < :cutoff"
                    ),
                    {"cutoff": cutoff},
                )
            ).scalar_one()
            if not count:
                continue
            line = f"{rule.table}: {count} row(s) older than {rule.window.days}d"
            (advisory if rule.basis is Basis.PROPOSED else overdue).append(line)

    if advisory:
        print("\n  PROPOSED windows with rows past them (not asserted):")
        for line in advisory:
            print(f"    {line}")

    assert overdue == [], (
        "rows have outlived a window that was not merely proposed:\n  "
        + "\n  ".join(overdue)
        + "\n\nRun `python scripts/purge_expired.py --apply`."
    )


# ---------------------------------------------------------------------------
# 4. Nothing deletes outside the registry
# ---------------------------------------------------------------------------


# Deletions that are a *person exercising a right*, not a retention policy.
#
# The first draft of the test below forbade every `DELETE` and immediately caught
# `alerts/service.py::delete_device`, which is the opposite of a problem: it runs
# on sign-out, and its own docstring gives the reason -- *"this is a user asking
# to stop being contacted, and the row holds a delivery address, so keeping it
# would be keeping contact details after being asked not to."* Forbidding that
# would have been a privacy test deleting a privacy feature.
#
# So the rule is narrower than "nothing deletes": **a time-based deletion belongs
# in the registry; a user-initiated one belongs in the feature, and is listed
# here.** Adding to this list is a claim that a human asked for the deletion.
_USER_INITIATED_DELETES: Final = {
    "app/alerts/service.py": (
        "delete_device, on sign-out. A hard delete rather than a disable because "
        "the row holds a delivery address and the user has asked not to be "
        "contacted. sent_alerts.device_id is ON DELETE SET NULL, so the "
        "de-duplication history survives the erasure."
    ),
}


def test_a_time_based_delete_may_only_live_in_the_registry() -> None:
    """
    A `DELETE FROM` driven by a clock is a retention rule, and it has to be declared.

    The specific regression this guards: the cheap way to stop a table growing is a
    `delete` in whichever agent noticed it growing, and then the window exists in one
    query, in one file, where no test can see it and no reader can find it.

    User-initiated deletions are exempt and enumerated in `_USER_INITIATED_DELETES`,
    with the reason, because a deletion someone asked for is a feature.
    """

    backend = _BACKEND
    registered = {rule.table for rule in PURGES}
    offenders: list[str] = []

    for path in sorted((backend / "app").rglob("*.py")):
        relative = path.relative_to(backend).as_posix()
        if relative in _USER_INITIATED_DELETES:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"delete\s+from\s+(?:public\.)?(\w+)", text, re.IGNORECASE):
            if match.group(1) in registered:
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{relative}:{line} -> {match.group(1)}")

    assert offenders == [], (
        "DELETE against a registered table, outside both the registry and the "
        "user-initiated allowlist. If a clock drives it, declare it in "
        "app/privacy/retention.py; if a person asked for it, add it to "
        f"_USER_INITIATED_DELETES with the reason: {offenders}"
    )


def test_the_user_initiated_allowlist_still_describes_real_code() -> None:
    """
    An allowlist entry for a file that no longer deletes anything is a hole left
    open for no reason — and the next genuine time-based delete in that file would
    walk straight through it.
    """

    backend = _BACKEND
    for relative, reason in _USER_INITIATED_DELETES.items():
        path = backend / relative
        assert path.is_file(), f"allowlisted file no longer exists: {relative}"
        assert re.search(r"delete\s+from", path.read_text(encoding="utf-8"), re.IGNORECASE), (
            f"{relative} is allowlisted for a user-initiated delete but issues none. "
            f"Remove the entry. Recorded reason was: {reason}"
        )


def test_the_expiry_sweep_marks_rather_than_deletes() -> None:
    """
    The distinction B14 is built on, asserted so it cannot erode.

    `expiry_sweep` says in its own docstring that it keeps expired rows *"because an
    expired row is the evidence that the surface retires things on its own."* If it
    ever starts deleting, that evidence goes and retention stops being a separate,
    declared concern.
    """

    backend = _BACKEND
    sweep = (backend / "app" / "agents" / "expiry_sweep.py").read_text(encoding="utf-8")
    assert "delete from" not in sweep.lower(), (
        "expiry_sweep must mark rows expired, not delete them; deletion belongs to "
        "app/privacy/retention.py and scripts/purge_expired.py"
    )
    assert "expired" in sweep


# ---------------------------------------------------------------------------
# 5. The purge actually deletes — proved, not assumed
# ---------------------------------------------------------------------------
#
# `test_no_row_is_older_than_its_declared_window` cannot fail yet: the project is
# eight days old and the shortest window is two days on an empty table, so every
# count is zero. A green result there says "nothing is overdue", not "deletion
# works". These two close that gap.


def test_a_naive_column_is_read_as_utc_explicitly() -> None:
    """
    The predicate builder, as a pure function.

    Eight columns in this schema are `timestamp without time zone` while the rest
    are `timestamptz`. The naive ones must be interpreted as UTC **in the SQL**, not
    by trusting the session's TimeZone to stay UTC — a retention window that changed
    meaning with a server setting would delete the wrong rows quietly.
    """
    import sys

    backend = _BACKEND
    sys.path.insert(0, str(backend / "scripts"))
    import purge_expired

    aware = next(rule for rule in tables_with_windows() if rule.table == "agent_runs")
    naive = next(rule for rule in tables_with_windows() if rule.table == "sos_incidents")

    assert "at time zone 'UTC'" not in purge_expired._predicate(aware, set())
    assert "at time zone 'UTC'" in purge_expired._predicate(
        naive, {("sos_incidents", "timestamp")}
    )


@pytest.mark.integration
async def test_the_purge_predicate_really_removes_an_overdue_row() -> None:
    """
    End to end against the real database, inside a transaction that is **rolled
    back**, so the live data is untouched.

    `agent_runs` is the subject deliberately: operational telemetry, no personal
    data, and a DERIVED window, so a mistake here costs a log line rather than
    somebody's record. The row is inserted a year old, counted as overdue, deleted
    by the same predicate the script uses, and confirmed gone — then the whole thing
    is discarded.

    Without this, B14 would ship a window, a registry and a script that had never
    deleted anything, and "expired data verifiably gone" would rest on reading the
    code.
    """
    import sys
    import uuid
    from datetime import UTC, datetime, timedelta

    backend = _BACKEND
    sys.path.insert(0, str(backend / "scripts"))
    import purge_expired

    try:
        from app.core.database import AsyncSessionLocal, engine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database configured: {exc}")

    from sqlalchemy import text as sql

    rule = next(rule for rule in tables_with_windows() if rule.table == "agent_runs")
    assert rule.basis is Basis.DERIVED, "this test deliberately uses a signed-off window"

    await engine.dispose(close=False)
    try:
        session = AsyncSessionLocal()
        await session.connection()
    except Exception as exc:
        pytest.skip(f"database unreachable: {type(exc).__name__}: {exc}")

    marker = f"b14-retention-probe-{uuid.uuid4()}"
    planted = datetime.now(UTC) - timedelta(days=365)
    where = purge_expired._predicate(rule, set())

    async with session as db:
        try:
            await db.execute(
                sql(
                    "insert into public.agent_runs "
                    "(run_id, agent, status, started_at, finished_at, created_at) "
                    "values (:run_id, :agent, 'ok', :at, :at, :at)"
                ),
                # `run_id` is NOT NULL with no default — the agents generate it.
                {"run_id": str(uuid.uuid4()), "agent": marker, "at": planted},
            )

            mine = sql("select count(*) from public.agent_runs where agent = :agent")
            assert (await db.execute(mine, {"agent": marker})).scalar_one() == 1, (
                "the probe row was not inserted, so the rest of this proves nothing"
            )

            overdue = (
                await db.execute(
                    sql(
                        f"select count(*) from public.agent_runs "  # noqa: S608
                        f"where agent = :agent and ({where})"
                    ),
                    {"agent": marker, "cutoff": datetime.now(UTC) - rule.window},
                )
            ).scalar_one()
            assert overdue == 1, "a year-old row was not counted as past a 90-day window"

            await db.execute(
                sql(f"delete from public.agent_runs where {where}"),  # noqa: S608
                {"cutoff": datetime.now(UTC) - rule.window},
            )
            assert (await db.execute(mine, {"agent": marker})).scalar_one() == 0, (
                "the purge predicate did not remove the overdue row"
            )
        finally:
            # Never committed. The probe row and the delete both disappear.
            await db.rollback()

    await engine.dispose(close=False)
    verify = AsyncSessionLocal()
    async with verify as db:
        left = (
            await db.execute(
                sql("select count(*) from public.agent_runs where agent = :agent"),
                {"agent": marker},
            )
        ).scalar_one()
    assert left == 0, "the probe row survived the rollback, so this test wrote to live data"


def test_proposed_windows_are_exactly_the_ones_awaiting_sign_off() -> None:
    """
    `proposed_windows()` is what `scripts/purge_expired.py` refuses to act on without
    `--force`, so it has to mean precisely that and nothing looser.

    Four of six windows are PROPOSED as of 2026-10-15 — `journeys`, `sos_incidents`,
    `gd_drafts`, `raw_documents`. That is the honest state: a retention period is a
    decision about somebody else's data, and nobody has made these.
    """
    proposed = proposed_windows()
    assert set(proposed) <= set(tables_with_windows()), "a PROPOSED rule that deletes nothing"
    assert all(rule.basis is Basis.PROPOSED for rule in proposed)
    assert all(rule.basis is not Basis.PROPOSED for rule in tables_with_windows() if rule not in proposed)
    assert proposed, (
        "no PROPOSED windows left. If every window has genuinely been signed off, say "
        "who and when in PROGRESS.md and delete this assertion -- do not flip a basis "
        "to DERIVED just to quiet the purge script."
    )
