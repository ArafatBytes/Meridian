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

Three layers enforce the same rule, and this file checks all three:

1. the `risk_flags_confirmed_needs_two_sources` CHECK constraint, verified by
   reading the migration (the database is not available in unit tests);
2. the fixture, which must not ship a confirmed flag with one source;
3. the seed loader's own validation, which refuses to build such a row.
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
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["flags"]


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
    """
    offenders: list[str] = []
    for flag in _fixture_flags():
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
    """
    offenders = [
        f["event_key"]
        for f in _fixture_flags()
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


def test_seed_loader_rejects_a_single_source_confirmed_flag(tmp_path, monkeypatch) -> None:
    """
    The seeder validates before it writes, and reports by flag name.

    This matters more than it looks: the loader is the one place a human types flag
    data, and a constraint violation arriving from Postgres names the constraint,
    not the flag. Catching it here means the message says which entry is wrong.
    """
    import sys

    sys.path.insert(0, str(BACKEND / "scripts"))
    import seed_risk_flags

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
    monkeypatch.setattr(seed_risk_flags, "FIXTURE", fixture)

    from datetime import UTC, datetime

    with pytest.raises(SystemExit):
        seed_risk_flags.build_rows(datetime.now(UTC))
