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


def test_schema_requires_a_confirmed_flag_to_cite_somebody() -> None:
    """
    The rule as the **final** schema states it, not as one migration states it.

    This test used to read `20261007120000__risk_flags.sql` alone and assert
    `source_count >= 2`. That was the right shape and the wrong scope, and
    `independence.py` said so in writing before it happened: a later migration
    weakening the CHECK would leave this passing over the hole, because the text
    of an applied migration never changes.

    So it reads **every** migration in order and tracks what the constraint is by
    the end. `20261016150000__a_vetted_newsroom_is_confirmation.sql` drops the
    two-source CHECK and adds `risk_flags_confirmed_cites_a_source`, which is a
    weaker rule deliberately -- see that file -- but not a vacuous one:
    `risk_flags_sources_match_count` ties `source_count` to the `sources` array,
    so this says a confirmed flag must name a publisher.
    """
    applied = sorted((BACKEND / "migrations" / "versions").glob("*.sql"))
    assert applied, "no migrations found"
    combined = re.sub(r"\s+", " ", "\n".join(p.read_text(encoding="utf-8") for p in applied))

    assert "drop constraint if exists risk_flags_confirmed_needs_two_sources" in combined, (
        "the two-source CHECK is expected to have been dropped on 2026-10-16; if it "
        "is back, this test and VETTED_PUBLISHERS disagree about what confirmed means"
    )
    assert "check (status <> 'confirmed' or source_count >= 1)" in combined, (
        "a confirmed flag must still cite at least one source. Dropping that too "
        "would allow an unattributable confirmed claim, which "
        "`policy/attribution.py` refuses to publish anyway."
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


def test_every_confirmed_fixture_flag_cites_a_publisher() -> None:
    """
    Mirrors `risk_flags_confirmed_cites_a_source`. The fixture is served by
    `SeededRiskSurface` with no database behind it, so the rule has to be checked
    here as well as in Postgres.
    """
    from datetime import UTC, datetime

    from app.scoring.fixture import fixture_rows

    # The loaded rows, not the JSON: most entries omit `sources` and the loader
    # generates them, so reading the file would ask the wrong question.
    offenders = [
        row["event_key"]
        for row in fixture_rows(datetime.now(UTC), include_chronic=True)
        if row["status"] == "confirmed"
        and (row["source_count"] < 1 or not row["sources"])
    ]
    assert offenders == [], (
        f"{offenders} are marked confirmed while citing nobody. A confirmed flag "
        "names the publisher that said it."
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


def test_the_loader_accepts_a_single_source_confirmed_flag(tmp_path) -> None:
    """
    The 2026-10-16 change, at the layer that validates the fixture.

    This test previously asserted the opposite, and the assertion was the right
    one while `confirmed` meant two independent publishers. It is inverted rather
    than deleted because the loader is still the only thing standing between a bad
    fixture entry and an offline demo: `SeededRiskSurface` reads these rows with
    no database behind it, so what the loader permits is what gets served.

    `test_the_loader_still_rejects_a_confirmed_flag_citing_nobody` is the rule
    that replaced it.
    """
    from app.scoring.fixture import fixture_rows

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

    rows = fixture_rows(datetime.now(UTC), include_chronic=False, fixture_path=fixture)
    assert rows, "a single-source confirmed flag is legal since 2026-10-16"
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["sources"], "and it must still cite somebody"


def test_the_loader_still_rejects_a_confirmed_flag_citing_nobody(tmp_path) -> None:
    """
    What replaced the two-source rule, at this layer.

    A confirmed flag that names no publisher is an unattributable claim, which
    `policy/attribution.py` refuses to publish and
    `risk_flags_confirmed_cites_a_source` refuses to store. The loader catches it
    first and says which entry is wrong -- a constraint violation arriving from
    Postgres names the constraint, not the flag.
    """
    import json

    from app.scoring.fixture import FixtureError, fixture_rows

    bad = {
        "flags": [
            {
                "event_key": "seed-bad-unattributed",
                "kind": "fire",
                "status": "confirmed",
                "place": "Bangshal",
                "lat": 23.71,
                "lon": 90.41,
                "radius_m": 400,
                "severity_0": 70,
                "half_life_hours": 3.5,
                "mobility_impact": "road_blocked",
                "observed_offset_hours": -1.0,
                "source_count": 0,
                "sources": [],
            }
        ]
    }
    fixture = tmp_path / "risk_flags.json"
    fixture.write_text(json.dumps(bad), encoding="utf-8")

    from datetime import UTC, datetime

    with pytest.raises(FixtureError, match="seed-bad-unattributed"):
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
        "this is the corroboration threshold for anything un-vetted; below 2 it "
        "would mean a single anonymous source confirms"
    )

    # **What the 2026-10-16 change did and did not do.** One outlet publishing
    # three times is still *one* publisher, and that is what `source_count`
    # reports on the flag sheet -- a follow-up never inflates corroboration.
    # What changed is that Channel 24 is vetted, so the flag is confirmed on the
    # strength of being Channel 24's, not on the strength of being three
    # articles. The distinction matters the moment an un-vetted source appears.
    one_outlet_three_articles = ["channel24", "channel24", "channel24"]
    assert len(independent_publishers(one_outlet_three_articles)) == 1
    assert not is_confirmable(
        ["some_blog", "some_blog", "some_blog"],
        minimum=settings.MIN_SOURCES_FOR_CONFIRMED,
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

    The regression this prevents has changed shape rather than gone away.
    `flag_row()` used to hard-code `"status": "unconfirmed"`, and the cheap way to
    make the map look better was to change that word. It now writes `confirmed`
    **conditionally**, gated on `is_vetted`, and the cheap bad version is to drop
    the condition -- so the rule is no longer "nobody but the guard writes it" but
    "nobody writes it unconditionally".

    `live_risk.py` is allowed to write it because a separate test asserts its
    write is gated; `rumour_guard.py` is allowed because promotion is its job.
    """
    import re

    allowed = {"rumour_guard.py", "live_risk.py"}
    offenders: list[str] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        if path.name in allowed:
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
        from app.core.database import AsyncSessionLocal, engine
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database configured: {exc}")

    # `asyncio_mode = "auto"` gives every async test its own event loop, while
    # `engine` is a module-level singleton whose pooled connections belong to
    # whichever loop first touched them. Run alone, this test passed; run after
    # the rest of the suite it **skipped itself** with
    # `database unreachable: RuntimeError` -- the connection was attached to a
    # loop that no longer existed, and the broad `except` below reported that as
    # an absent database. So the project's central corroboration invariant was
    # quietly not running in CI, which is the worst way for a safety check to
    # fail. `close=False` matters: a plain dispose tries to shut the dead loop's
    # connections and raises. Same trap and same fix as
    # `test_retention_is_declared.py`, which documents it at length.
    await engine.dispose(close=False)

    # Only the connect is guarded. The query itself must be allowed to fail
    # loudly: a broken invariant has to look different from an absent database.
    try:
        connection = AsyncSessionLocal()
        await connection.connection()
    except Exception as exc:
        pytest.skip(f"database unreachable: {type(exc).__name__}: {exc}")

    async with connection as db:
        rows = (
            await db.execute(
                sql(
                    "select event_key, status, source_count, sources::text as sources_json "
                    "from public.risk_flags where status = 'confirmed'"
                )
            )
        ).mappings().all()

    from app.core.config import settings
    from app.policy.independence import independent_publishers, is_confirmable

    offenders: list[str] = []
    for row in rows:
        refs = json.loads(row["sources_json"] or "[]")
        ids = [str(r.get("source_id", "")) for r in refs if r.get("source_id")]
        # The 2026-10-16 rule, not the old one: confirmed means *either* a vetted
        # newsroom published it *or* two independent publishers agreed. Asserting
        # two publishers here contradicted the policy this file is named after,
        # and only failed once live ingestion actually wrote a confirmed
        # single-source flag -- so the test outlived the rule by a day.
        if not is_confirmable(ids, minimum=settings.MIN_SOURCES_FOR_CONFIRMED):
            offenders.append(
                f"{row['event_key']} claims source_count={row['source_count']} but cites "
                f"publishers {sorted(independent_publishers(ids))}, none of them vetted"
            )

    assert offenders == [], (
        "confirmed flags in the database that neither cite a vetted publisher nor are "
        "corroborated by two independent ones:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# 5. Authority is weight, not confirmation — B11a, 2026-10-15
# ---------------------------------------------------------------------------
#
# DMP News is the police's own outlet, so a newspaper reprinting its release adds
# no independent verification. The owner's first instinct was to let one DMP
# report reach `confirmed`; the database says otherwise, and these tests pin the
# resolution so the question cannot be quietly reopened in code.


def test_the_vetted_list_is_exactly_the_list_we_ingest() -> None:
    """
    **The drift guard, and the most important test in this file now.**

    `VETTED_PUBLISHERS` is `SOURCES` restated, because importing `SOURCES` into
    the policy module would drag the fetcher and every parser into the routing
    request path. Restating it means it can rot, and rotting in either direction
    is bad in a different way:

    * a publisher in `SOURCES` but not here is ingested and then drawn as a
      hollow unconfirmed pin, which is the bug this whole change set out to fix;
    * a publisher here but not in `SOURCES` is an outlet nobody surveyed being
      granted single-source confirmation -- the direction that actually costs
      something.
    """
    from app.ingestion.sources import SOURCES
    from app.policy.independence import VETTED_PUBLISHERS

    ingested = {source.source_id for source in SOURCES}
    assert VETTED_PUBLISHERS == ingested, (
        "VETTED_PUBLISHERS and SOURCES have drifted.\n"
        f"  ingested but not vetted: {sorted(ingested - VETTED_PUBLISHERS)}\n"
        f"  vetted but not ingested: {sorted(VETTED_PUBLISHERS - ingested)}"
    )


def test_one_vetted_publisher_is_enough() -> None:
    """
    The 2026-10-16 decision, stated once. A national newsroom does not invent a
    fire, and 79% of the live surface was hollow because the old rule treated
    Prothom Alo as an anonymous claimant.
    """
    from app.core.config import settings
    from app.policy.independence import VETTED_PUBLISHERS, is_confirmable

    for publisher in sorted(VETTED_PUBLISHERS):
        assert is_confirmable([publisher], minimum=settings.MIN_SOURCES_FOR_CONFIRMED), (
            f"{publisher} is a publisher we chose and checked; one of its reports "
            "is enough for `confirmed`."
        )


def test_an_unvetted_source_still_needs_corroboration() -> None:
    """
    The other half, and the reason `is_confirmable` kept its counting branch.

    Nothing un-vetted is ingested today, so this is a rule about the future: the
    moment something is read that was not hand-picked -- a community cluster, a
    new feed added in a hurry -- it reaches `confirmed` the old way or not at all.
    """
    from app.core.config import settings
    from app.policy.independence import is_confirmable

    minimum = settings.MIN_SOURCES_FOR_CONFIRMED
    assert not is_confirmable(["some_blog"], minimum=minimum)
    assert not is_confirmable([], minimum=minimum)
    assert is_confirmable(["some_blog", "another_blog"], minimum=minimum)


def test_authority_is_expressed_as_full_weight() -> None:
    """
    What the grant actually is: an official report is not discounted as a rumour.

    `expired` and `rejected` must stay at 0.0 even for an authoritative publisher —
    the carve-out lives inside the `unconfirmed` branch precisely so that a flag
    which is no longer served cannot contribute through it.
    """
    from app.policy.independence import UNCONFIRMED_WEIGHT, confidence

    # A vetted publisher's flag is promoted at write time now, so this branch is
    # reached only by rows written before 2026-10-16. It must still not discount
    # a newsroom as though it were a rumour.
    assert confidence("unconfirmed", ["dmp_news"]) == 1.0
    assert confidence("unconfirmed", ["prothom_alo"]) == 1.0
    # A source nobody surveyed is still worth less than a corroborated claim.
    assert confidence("unconfirmed", ["some_blog"]) == UNCONFIRMED_WEIGHT
    assert confidence("unconfirmed") == UNCONFIRMED_WEIGHT, "the default must not change"
    for dead in ("expired", "rejected"):
        assert confidence(dead, ["dmp_news"]) == 0.0, dead


def test_the_authoritative_set_is_a_tripwire_not_a_config_knob() -> None:
    """
    **This set is dangerous in the direction `_SAME_OWNER` is not.**

    An entry in the ownership map can only ever *reduce* what we are willing to
    trust, so recording one is safe even when the map is incomplete. An entry here
    *increases* the weight of a single source, and there is no permissive default to
    fall back on. So the membership is asserted, and widening it has to be a
    deliberate change to this test alongside a decision about a named institution.

    If you are here because this test failed: that is the test working. Say in the
    handoff who decided, and why that body is the primary record of what it reports
    rather than a claim about it.
    """
    from app.ingestion.sources import SOURCES
    from app.policy.independence import AUTHORITATIVE_PUBLISHERS

    assert AUTHORITATIVE_PUBLISHERS == {"dmp_news"}, (
        "the authoritative set has changed. Every member must be the primary record "
        "of what it reports -- not a well-regarded outlet, and not a government body "
        "that merely sounds official."
    )

    # An authoritative id that no source produces would be dead policy, and the
    # silent kind: nothing would ever be weighted by it and nothing would say so.
    known = {source.source_id for source in SOURCES}
    assert AUTHORITATIVE_PUBLISHERS <= known, (
        f"authoritative publishers absent from SOURCES: {AUTHORITATIVE_PUBLISHERS - known}"
    )


def test_both_surfaces_weight_an_authoritative_source_the_same_way() -> None:
    """
    `DbRiskSurface` and `SeededRiskSurface` derive `confidence` independently, so a
    policy change applied to one and not the other is the standing hazard here —
    which is what `test_surfaces_agree` exists for generally. This checks the
    specific thing B11a added: both call sites pass their publishers through.
    """
    db = (BACKEND / "app" / "scoring" / "surface_db.py").read_text(encoding="utf-8")
    seeded = (BACKEND / "app" / "scoring" / "surface_seeded.py").read_text(encoding="utf-8")
    for name, text in (("surface_db.py", db), ("surface_seeded.py", seeded)):
        assert "confidence(" in text, name
        call = text[text.index("confidence(") :][:200]
        assert "source_id" in call, (
            f"{name} calls confidence() without passing its publishers, so an "
            "authoritative source would be silently discounted there"
        )
