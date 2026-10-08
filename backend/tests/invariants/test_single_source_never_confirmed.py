"""
Invariant: **verification before publication.**

Concept document §9, IMPLEMENTATION_PLAN.md §4: *no single unverified source
produces a confirmed flag.* `status` reaches `confirmed` only with two or more
independent `source_id`s, after semantic deduplication.

Rumour Guard — the component that does the promoting — is D05. This test lands in
D01 anyway, and that ordering is deliberate: D04 starts writing flags from live
news, every one of them from one source, and the test is what makes it impossible
for that sprint to quietly mark them confirmed because the map looks better that
way.

Four layers enforce the same rule, and this file checks all four:

1. the `risk_flags_confirmed_needs_two_sources` CHECK constraint, verified by
   reading the migration (the database is not available in unit tests);
2. the fixture, which must not ship a confirmed flag with one source;
3. the seed loader's own validation, which refuses to build such a row;
4. **the rows actually in the database**, and the promotion logic that puts them
   there. Added in D05, which is what `DEMO_PLAN.md` means by *"the invariant test
   from D01 now runs against real data, not a stub"* — until Rumour Guard existed
   there was no promotion path to test, only a fixture and a constraint.

Layers 1-3 need no database and run on every push. Layer 4 is marked `integration`
and skips when there is no database to ask, because a developer without Supabase
credentials should see the first three pass rather than a connection error.
"""

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
FIXTURE = BACKEND / "data" / "fixtures" / "risk_flags.json"
MIGRATION = BACKEND / "migrations" / "versions" / "20261007120000__risk_flags.sql"


def _fixture_flags() -> list[dict]:
    """The fixture entries, exactly as written in the file."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["flags"]


def _loaded_rows() -> list[dict]:
    """
    The rows the fixture actually produces, after the loader has filled in defaults.

    D02 made this distinction matter. A fixture entry is now allowed to omit its
    `sources` list, in which case `app/scoring/fixture.py` generates one sample
    reference per `source_count` — which is what keeps a 200-entry fixture to one line
    per flag. So the raw file no longer carries the provenance for most entries, and a
    test that read only the file would be checking a field that is usually absent and
    passing for the wrong reason.

    These rows are what the INSERT statement gets and what the seeded surface serves,
    so asserting against them is strictly stronger than asserting against the file.
    """
    from datetime import UTC, datetime

    from app.scoring.fixture import fixture_rows

    return fixture_rows(datetime.now(UTC))


# ---------------------------------------------------------------------------
# 1. The database will not store the violation
# ---------------------------------------------------------------------------


def test_schema_has_the_constraint() -> None:
    """
    The CHECK is present in the migration that creates `risk_flags`.

    Asserted by reading the SQL rather than by querying a database, so it runs in
    CI with no Postgres. It is a weaker check than executing it — but a migration
    is immutable once applied, so matching the text is sound here in a way it would
    not be for ordinary code.

    The constraint itself was executed against PostGIS 16 when it was written; what
    this test defends against is a later migration dropping it.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "risk_flags_confirmed_needs_two_sources" in sql, (
        "the CHECK that stops a single-source flag being confirmed is missing from "
        f"{MIGRATION.name}"
    )

    # Normalise whitespace: the constraint is written across several lines.
    normalised = re.sub(r"\s+", " ", sql)
    assert "check (status <> 'confirmed' or source_count >= 2)" in normalised, (
        "the constraint exists by name but its condition has changed. It must be "
        "`status <> 'confirmed' or source_count >= 2`."
    )


def test_schema_still_requires_a_positive_half_life() -> None:
    """
    The decay invariant's schema half, checked in the same place.

    Not strictly this test's subject, but it is the other CHECK the plan names
    explicitly, and the two are removed by the same kind of careless migration.
    """
    sql = re.sub(r"\s+", " ", MIGRATION.read_text(encoding="utf-8"))
    assert "risk_flags_half_life_positive" in sql
    assert "check (half_life_hours > 0)" in sql


# ---------------------------------------------------------------------------
# 2. The fixture obeys it
# ---------------------------------------------------------------------------


def test_no_confirmed_fixture_flag_has_fewer_than_two_sources() -> None:
    offenders = [
        f["event_key"]
        for f in _fixture_flags()
        if f.get("status") == "confirmed" and int(f.get("source_count", 1)) < 2
    ]
    assert offenders == [], (
        f"{offenders} are marked confirmed with a single source. A flag is "
        "confirmed only when two or more independent publishers agree."
    )


def test_confirmed_fixture_flags_cite_distinct_publishers() -> None:
    """
    Two reports from the same outlet are one source.

    `source_count` is a number anyone can type. This checks the `sources` list
    actually behind it: if a flag cites three entries that are all
    `prothom_alo`, that is one publisher agreeing with itself, which is exactly
    the failure mode Rumour Guard's deduplication exists to catch.

    Checked against the loaded rows rather than the raw file — see `_loaded_rows()`.
    """
    offenders: list[str] = []
    for flag in _loaded_rows():
        if flag.get("status") != "confirmed":
            continue
        publishers = {s["source_id"] for s in flag.get("sources", [])}
        if len(publishers) < 2:
            offenders.append(f"{flag['event_key']} (publishers: {sorted(publishers)})")
    assert offenders == [], (
        f"confirmed flags citing fewer than two distinct publishers: {offenders}"
    )


def test_no_fixture_flag_lists_more_sources_than_it_counts() -> None:
    """
    `source_count` may exceed the listed `sources` — Rumour Guard can count a
    corroboration whose full text it did not keep — but never the other way round.
    The database carries the same constraint.

    Checked against the loaded rows rather than the raw file — see `_loaded_rows()`.
    """
    offenders = [
        f["event_key"]
        for f in _loaded_rows()
        if len(f.get("sources", [])) > int(f.get("source_count", 1))
    ]
    assert offenders == [], f"{offenders} list more sources than source_count claims"


def test_the_fixture_actually_contains_both_statuses() -> None:
    """
    A fixture of nothing but unconfirmed flags would pass every test above and
    prove nothing. The demo also needs both, since D05's whole point is that the
    two look different on the map.
    """
    statuses = {f.get("status", "unconfirmed") for f in _fixture_flags()}
    assert "confirmed" in statuses, "no confirmed flags in the fixture"
    assert "unconfirmed" in statuses, "no unconfirmed flags in the fixture"


# ---------------------------------------------------------------------------
# 3. The loader refuses to build the violation
# ---------------------------------------------------------------------------


def test_the_loader_rejects_a_single_source_confirmed_flag(tmp_path) -> None:
    """
    The loader validates before anything writes, and reports by flag name.

    This matters more than it looks: the fixture is the one place a human types flag
    data, and a constraint violation arriving from Postgres names the constraint, not
    the flag. Catching it here means the message says which entry is wrong.

    It also now guards the surface that has no constraints at all.
    `SeededRiskSurface` reads these same rows with no database behind it, so this
    check is the only thing standing between a bad fixture entry and an offline demo
    serving a flag the real database would have refused.
    """
    from app.scoring.fixture import FixtureError, fixture_rows

    bad = {
        "flags": [
            {
                "event_key": "seed-bad-confirmed",
                "kind": "fire",
                "status": "confirmed",
                "place": "Bangshal",
                "lat": 23.71,
                "lon": 90.40,
                "radius_m": 400,
                "severity_0": 70,
                "half_life_hours": 3.5,
                "mobility_impact": "road_blocked",
                "observed_offset_hours": -1,
                "source_count": 1,
                "sources": [
                    {
                        "source_id": "prothom_alo",
                        "url": "https://example.test/x",
                        "published_offset_hours": -1,
                    }
                ],
            }
        ]
    }
    fixture = tmp_path / "risk_flags.json"
    fixture.write_text(json.dumps(bad), encoding="utf-8")

    from datetime import UTC, datetime

    with pytest.raises(FixtureError, match="seed-bad-confirmed"):
        fixture_rows(datetime.now(UTC), include_chronic=False, fixture_path=fixture)


def test_the_seeder_turns_a_fixture_error_into_an_exit_code() -> None:
    """
    The exception above has to reach the shell as a failure, not as a traceback.

    `scripts/seed_risk_flags.py` is run by hand and by `seed.sh`, and a loader error
    that escaped as an unhandled exception would still exit non-zero — but it would
    print a traceback where the message naming the bad entry should be, which defeats
    the point of validating by name.

    **This reads the script's source**, because the script resolves the fixture path
    itself and offers no way to point it at a bad one; making it injectable purely to
    test this would be a worse trade than a source check that says so out loud.
    """
    source = (BACKEND / "scripts" / "seed_risk_flags.py").read_text(encoding="utf-8")
    assert "except FixtureError" in source, (
        "seed_risk_flags.py must catch FixtureError and return a non-zero exit code"
    )
    assert "return 2" in source


# ---------------------------------------------------------------------------
# 4. The promotion path, and the rows it has actually written
# ---------------------------------------------------------------------------
#
# D05. Everything above this line is true of a fixture file and a migration's text.
# None of it would have noticed a Rumour Guard that promoted on one publisher,
# because before D05 nothing promoted at all.


def test_promotion_needs_two_independent_publishers_not_two_articles() -> None:
    """
    The decision itself, taken straight from the module that makes it.

    `merge_into()` recomputes `source_count` through
    `policy.independence.independent_publishers` and promotes only when that reaches
    `MIN_SOURCES_FOR_CONFIRMED`. The failure this guards against is the tempting one:
    incrementing a counter per article, so an outlet publishing a follow-up
    corroborates itself and `confirmed` comes to mean "written about twice".
    """
    from app.core.config import settings
    from app.policy.independence import independent_publishers, is_confirmable

    assert settings.MIN_SOURCES_FOR_CONFIRMED >= 2, (
        "lowering this below 2 contradicts the database CHECK, which would reject the "
        "insert -- but it would also mean the code intended to"
    )

    one_outlet_three_articles = ["channel24", "channel24", "channel24"]
    assert len(independent_publishers(one_outlet_three_articles)) == 1
    assert not is_confirmable(
        one_outlet_three_articles, minimum=settings.MIN_SOURCES_FOR_CONFIRMED
    )

    two_outlets = ["channel24", "ekattor_tv"]
    assert is_confirmable(two_outlets, minimum=settings.MIN_SOURCES_FOR_CONFIRMED)


def test_the_merge_statement_cannot_set_confirmed_without_recounting() -> None:
    """
    Read the guard's own SQL: `status` and `source_count` are always written together.

    A merge that updated `status` while leaving `source_count` alone would satisfy
    every test above and still violate the invariant at runtime, because the CHECK
    compares the two columns. They move together or not at all.

    This is a source check, for the same reason `test_the_seeder_turns_a_fixture_error
    _into_an_exit_code` is one: the alternative is reaching into a module's private
    SQL string from a test, and saying so out loud is better than pretending.
    """
    guard = (BACKEND / "app" / "agents" / "rumour_guard.py").read_text(encoding="utf-8")
    merge = guard[guard.index("_MERGE: Final"):]
    merge = merge[: merge.index('"""', merge.index('"""') + 3)]
    assert "source_count = :source_count" in merge
    assert "status       = :status" in merge, (
        "the merge must write status and source_count in the same statement; the CHECK "
        "constraint compares them, so updating one without the other is how a "
        "single-source confirmed flag would get written"
    )


def test_nothing_writes_confirmed_except_the_guard() -> None:
    """
    `status = 'confirmed'` must not appear in any INSERT outside Rumour Guard.

    The specific regression this prevents: D04's `LiveRiskAgent` hard-codes
    `"status": "unconfirmed"` in `flag_row()`, and the cheap way to make the map look
    better is to change that word. Then one article would produce a confirmed flag and
    the only thing standing in the way would be the database.

    Scoped to `app/`, and `rumour_guard.py` is the one allowed producer.
    """
    import re

    offenders: list[str] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        if path.name == "rumour_guard.py":
            continue
        text = path.read_text(encoding="utf-8")
        # A literal assignment of the word, not a comparison or a docstring mention.
        for match in re.finditer(r"""["']status["']\s*:\s*["']confirmed["']""", text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(BACKEND)}:{line}")

    assert offenders == [], (
        "only app/agents/rumour_guard.py may write status='confirmed', because it is "
        f"the only module that counts independent publishers first. Found: {offenders}"
    )


@pytest.mark.integration
async def test_no_row_in_the_database_is_confirmed_on_one_publisher() -> None:
    """
    The real-data check: every `confirmed` row, as it actually exists.

    This is the one test in this file that could catch a Rumour Guard bug in
    production data rather than in intent. It reads `sources` and counts *distinct
    publishers*, not `source_count` — a count that agrees with itself proves nothing,
    and the whole failure mode is the two drifting apart.

    Skips rather than fails when there is no database. A developer without Supabase
    credentials should see layers 1-3 pass, not a connection error dressed as an
    invariant violation.
    """
    import json

    from sqlalchemy import text as sql

    try:
        from app.core.database import AsyncSessionLocal
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database configured: {exc}")

    try:
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    sql(
                        "select event_key, status, source_count, sources::text as sources_json "
                        "from public.risk_flags where status = 'confirmed'"
                    )
                )
            ).mappings().all()
    except Exception as exc:
        pytest.skip(f"database unreachable: {type(exc).__name__}")

    from app.policy.independence import independent_publishers

    offenders: list[str] = []
    for row in rows:
        refs = json.loads(row["sources_json"] or "[]")
        publishers = independent_publishers(
            str(r.get("source_id", "")) for r in refs if r.get("source_id")
        )
        if len(publishers) < 2:
            offenders.append(
                f"{row['event_key']} claims source_count={row['source_count']} but cites "
                f"publishers {sorted(publishers)}"
            )

    assert offenders == [], (
        "confirmed flags in the database that are not corroborated by two independent "
        "publishers:\n  " + "\n  ".join(offenders)
    )
