"""
The corroboration agent: how reports become one cluster, and what it refuses to do.

Companion to `test_one_report_is_never_published.py`, which pins the threshold. This
pins the mechanics around it — the grouping, the eligibility gates, and three
refusals that are each a way the pipeline could go quietly wrong:

* it must never write `risk_flags`;
* it must never read a report's narrative;
* a takedown must hold across runs, and a faded cluster must not resurrect.

Everything here is a pure function or a source scan, so none of it needs a
database. The clustering is the part most worth testing that way: it is geometry,
it has edge cases that are tedious to arrange in Postgres, and it is where an
over-merge would turn "this corner" into "this neighbourhood".
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.report_corroboration import Candidate, group_by_proximity
from app.policy.community import (
    CLUSTER_RADIUS_M,
    CLUSTER_WINDOW,
    MIN_ACCOUNT_AGE_HOURS,
    ReportFamily,
    eligible_reporters,
    family_for_category,
    independent_reporters,
)

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
AGENT = BACKEND / "app" / "agents" / "report_corroboration.py"

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)

# Dhaka. ~0.0000090 degrees of latitude is a metre, near enough for a test.
BASE_LAT = 23.7465
BASE_LON = 90.3760
METRE_IN_DEGREES_LAT = 1.0 / 111_320.0


def _at(metres_north: float, *, user: str, family: str = "theft", hours: int = 0) -> Candidate:
    return Candidate(
        report_id=uuid4(),
        user_id=user,
        family=family_for_category(family),
        lat=BASE_LAT + metres_north * METRE_IN_DEGREES_LAT,
        lon=BASE_LON,
        incident_at=NOW - timedelta(hours=hours),
    )


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def test_two_nearby_reports_of_one_family_group_together() -> None:
    groups = group_by_proximity([_at(0, user="a"), _at(50, user="b")])
    assert len(groups) == 1
    assert groups[0].reporter_count == 2


def test_two_distant_reports_stay_apart() -> None:
    groups = group_by_proximity([_at(0, user="a"), _at(CLUSTER_RADIUS_M * 3, user="b")])
    assert len(groups) == 2


def test_different_families_never_corroborate_each_other() -> None:
    """
    A burglary and an assault on one corner are two unrelated incidents. Merging
    them would mean three different things happening nearby corroborating each
    other, and a cluster that is the sum of everything that ever happened says
    nothing.
    """
    groups = group_by_proximity(
        [_at(0, user="a", family="theft"), _at(10, user="b", family="assault")]
    )
    assert len(groups) == 2
    assert {g.family for g in groups} == {ReportFamily.PROPERTY, ReportFamily.VIOLENT}


def test_theft_and_robbery_do_corroborate() -> None:
    """
    The under-merging failure Rumour Guard warns about, in this domain: two people
    describing one snatching will often pick different categories. If these split,
    corroboration that arrived is counted as two separate claims and neither ever
    publishes.
    """
    groups = group_by_proximity(
        [_at(0, user="a", family="theft"), _at(20, user="b", family="robbery")]
    )
    assert len(groups) == 1
    assert groups[0].reporter_count == 2


def test_fraud_is_not_clustered_with_property_crime() -> None:
    """
    Fraud is not a property of a place -- it happens over a phone or a counter.
    Clustering it by location would produce a map of where victims were standing.
    """
    assert family_for_category("fraud") is ReportFamily.OTHER
    assert family_for_category("theft") is ReportFamily.PROPERTY


def test_a_chain_of_reports_does_not_grow_without_bound() -> None:
    """
    The single-link failure, and the reason grouping compares against the centroid
    rather than the nearest member.

    Five reports in a line, each 150 m from the last (inside `CLUSTER_RADIUS_M`),
    span 600 m end to end. Nearest-member linking would make them one cluster
    600 m across -- a neighbourhood, which is the area label concept document
    section 9 forbids. Centroid linking must not.
    """
    step = CLUSTER_RADIUS_M * 0.75
    chain = [_at(step * i, user=f"u{i}") for i in range(5)]
    groups = group_by_proximity(chain)

    assert len(groups) > 1, "centroid linking must break a long chain into clusters"
    for group in groups:
        spread = max(m.lat for m in group.members) - min(m.lat for m in group.members)
        assert spread / METRE_IN_DEGREES_LAT <= CLUSTER_RADIUS_M * 2


def test_grouping_is_deterministic() -> None:
    """
    The reconcile step compares one run against the last. If grouping depended on
    input order beyond the agent's own oldest-first sort, a cluster's identity -- and
    therefore its `corroborated_at` and any takedown on it -- would shuffle between
    runs.
    """
    reports = [_at(i * 40, user=f"u{i}", hours=i) for i in range(6)]
    first = [len(g.members) for g in group_by_proximity(reports)]
    second = [len(g.members) for g in group_by_proximity(list(reports))]
    assert first == second


def test_ten_reports_from_one_account_are_one_reporter() -> None:
    """
    The whole point of counting reporters rather than reports. Volume from one
    person must be worth nothing, exactly as a same-outlet follow-up is in Rumour
    Guard.
    """
    groups = group_by_proximity([_at(i * 5, user="same") for i in range(10)])
    assert len(groups) == 1
    assert len(groups[0].members) == 10
    assert groups[0].reporter_count == 1


def test_independent_reporters_collapses_duplicates() -> None:
    assert independent_reporters(["a", "a", "a", "b"]) == {"a", "b"}


def test_a_group_reports_its_window_from_its_members() -> None:
    group = group_by_proximity(
        [_at(0, user="a", hours=100), _at(30, user="b", hours=4)]
    )[0]
    assert group.observed_at == NOW - timedelta(hours=4)
    assert group.first_report_at == NOW - timedelta(hours=100)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def _report(
    *,
    user: str,
    status: str = "filed",
    incident_hours_ago: int = 48,
    account_age_hours_at_incident: float = MIN_ACCOUNT_AGE_HOURS + 1,
) -> dict:
    incident = NOW - timedelta(hours=incident_hours_ago)
    return {
        "user_id": user,
        "status": status,
        "incident_date_time": incident,
        "account_created_at": incident - timedelta(hours=account_age_hours_at_incident),
    }


def test_a_withdrawn_report_does_not_corroborate() -> None:
    """
    The author retracted it. The row stays -- deleting it would destroy the audit
    trail of a cluster already published on its strength -- but it stops counting.
    """
    eligible = eligible_reporters(
        [_report(user="a"), _report(user="b", status="withdrawn")]
    )
    assert [r["user_id"] for r in eligible] == ["a"]


def test_a_removed_report_does_not_corroborate() -> None:
    eligible = eligible_reporters([_report(user="a", status="removed")])
    assert eligible == []


def test_an_account_created_after_the_incident_does_not_corroborate() -> None:
    """
    The anti-sybil gate. Without it three throwaway signups corroborate anything in
    five minutes.
    """
    eligible = eligible_reporters(
        [_report(user="a", account_age_hours_at_incident=-10.0)]
    )
    assert eligible == []


def test_the_account_age_gate_is_measured_against_the_incident() -> None:
    """
    Not against the filing time. Measured against filing, an attacker waits a day
    and the gate becomes a delay rather than a cost.
    """
    just_too_new = _report(
        user="a", account_age_hours_at_incident=MIN_ACCOUNT_AGE_HOURS - 0.5
    )
    just_old_enough = _report(
        user="b", account_age_hours_at_incident=MIN_ACCOUNT_AGE_HOURS + 0.5
    )
    eligible = eligible_reporters([just_too_new, just_old_enough])
    assert [r["user_id"] for r in eligible] == ["b"]


def test_a_report_with_no_account_age_is_refused_not_waved_through() -> None:
    """An unapplied gate must not pass silently."""
    broken = _report(user="a")
    broken["account_created_at"] = None
    assert eligible_reporters([broken]) == []


def test_one_report_per_account_counts() -> None:
    eligible = eligible_reporters(
        [
            _report(user="a", incident_hours_ago=100),
            _report(user="a", incident_hours_ago=10),
            _report(user="b", incident_hours_ago=20),
        ]
    )
    assert sorted(r["user_id"] for r in eligible) == ["a", "b"]


def test_the_surviving_report_per_account_is_the_earliest() -> None:
    """
    Which one survives must not depend on how the groups happened to form, so it is
    decided here, over the whole window, by incident time.
    """
    eligible = eligible_reporters(
        [
            _report(user="a", incident_hours_ago=10),
            _report(user="a", incident_hours_ago=100),
        ]
    )
    assert len(eligible) == 1
    assert eligible[0]["incident_date_time"] == NOW - timedelta(hours=100)


# ---------------------------------------------------------------------------
# Refusals, read out of the source
# ---------------------------------------------------------------------------


def _agent_source() -> str:
    return AGENT.read_text(encoding="utf-8")


def test_the_agent_never_writes_risk_flags() -> None:
    """
    Defect 54 proposes bridging reports into `risk_flags`, and that bridge is the
    one thing this agent must not build. A risk flag is a mobility claim;
    `MobilityImpact`'s six values are all about traffic flow, and a corner where
    people were robbed is not a road that is blocked. `policy/framing.py` bans the
    vocabulary besides.

    So the pipeline ends in `community_clusters`. If a later sprint reaches for
    `risk_flags` here, this is what says no.
    """
    source = _agent_source()
    statements = source.split('text(\n    """')
    for statement in statements[1:]:
        body = statement.split('"""')[0].lower()
        assert "risk_flags" not in body, "the corroboration agent must not touch risk_flags"


def test_the_agent_never_selects_a_reports_narrative() -> None:
    """
    A cluster that cannot see the text cannot leak it. The candidate query selects
    no title, description, location name or evidence path -- checked here because the
    column list is the only thing standing between an audit trail and a public
    record of what victims wrote.
    """
    candidates = _agent_source().split("_CANDIDATES: Final = text(", 1)[1].split(")", 1)[0]
    for column in ("title", "description", "location_name", "evidence_photo_path",
                   "vision_analysis"):
        assert column not in candidates, f"{column} must not reach the corroboration agent"


def test_the_agent_stores_a_pseudonym_rather_than_a_user_id() -> None:
    source = _agent_source()
    assert "_reporter_ref(" in source
    assert "hmac.new(" in source
    # The stored JSON must carry `reporter_ref`, never `user_id`. Sliced to the next
    # parameter rather than to a bracket -- the block contains brackets of its own.
    reports_json = source.split('"reports": json.dumps(', 1)[1].split('"severity_0"', 1)[0]
    assert "reporter_ref" in reports_json
    # The *stored keys*, not every mention: `member.user_id` legitimately appears
    # here as the argument being hashed. What must never appear is a `"user_id"` key
    # in the JSON, which is what would make community_clusters a map of who reported
    # what.
    assert '"user_id"' not in reports_json
    assert '"title"' not in reports_json
    assert '"description"' not in reports_json
    assert '"category"' not in reports_json


def test_a_takedown_is_never_undone_by_a_later_run() -> None:
    """
    `removed` is the only human lever in this design. A run that could not see a
    removed cluster would create a fresh one at the same corner within the hour and
    quietly undo the takedown.
    """
    source = _agent_source()
    assert "ClusterStatus.REMOVED" in source
    assert "_EXISTING_CLUSTERS" in source
    # It reads every cluster, not only the live ones -- that is what makes the lever
    # visible to the next run.
    existing = source.split("_EXISTING_CLUSTERS: Final = text(", 1)[1].split('"""', 2)[1]
    assert "where status" not in existing.lower()


def test_a_faded_cluster_is_not_resurrected_without_new_evidence() -> None:
    """
    A cluster's decay runs out about ten days past its newest report while the
    candidate window is a fortnight, so an agent that only looked at live rows would
    re-insert the same pattern at full severity on a timer.
    """
    source = _agent_source()
    assert "ClusterStatus.EXPIRED" in source
    assert "group.observed_at <= previous" in source


def test_the_candidate_window_matches_the_policy() -> None:
    """
    The agent must not carry its own window. `CLUSTER_WINDOW` is paired with
    `CLUSTER_HALF_LIFE_HOURS` so a cluster serves for about as long as the window
    that built it; a second constant here would break that pairing silently.
    """
    source = _agent_source()
    assert "ctx.now - CLUSTER_WINDOW" in source
    assert CLUSTER_WINDOW == timedelta(days=14)


# ===========================================================================
# Defect 57 — the agent that had never once succeeded
# ===========================================================================


class _RecordingSession:
    """
    Enough `AsyncSession` to drive `run()` with no database.

    Every `execute` is recorded and answers empty, so the publish loop never
    runs and the agent completes its bookkeeping. The point is not the result;
    it is the parameters that reached the driver.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def execute(self, statement: object, params: dict[str, object] | None = None) -> object:
        self.calls.append((str(statement), params))

        class _Empty:
            def all(self) -> list[object]:
                return []

            def first(self) -> None:
                return None

            def scalar_one_or_none(self) -> None:
                return None

        return _Empty()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def test_the_window_is_bound_naive_because_the_column_is_naive() -> None:
    """
    Defect 57, found by B9's fleet status on 15 Oct: **38 runs, 0 successes.**
    This agent had never worked, `community_clusters` held zero rows, and three
    documents described B13 as landed.

    `crime_reports.incident_date_time` is `timestamp without time zone`, and
    asyncpg refuses to encode an aware datetime into one — it raises while
    binding, before the statement is sent, so the run died on its first query
    every hour. Nothing noticed because a failed run writes an `agent_runs` row
    and no alert, and nothing read `agent_runs` back.

    The agent already read the naive column correctly on the way *out*
    (`_rows_to_candidates` applies UTC). Only the bound parameter was missed, so
    this asserts the direction that was wrong rather than the one that was right.

    Checked through `run()` rather than by reading the source, because the bug
    was not visible in the SQL — `where r.incident_date_time >= :since` is
    correct — it was in the value handed to it.
    """
    from app.agents.report_corroboration import AGENT
    from app.contracts.agents import AgentContext

    session = _RecordingSession()
    # `model_construct`, not `AgentContext(...)`: `db` is isinstance-validated
    # against `AsyncSession`, and the alternative — a `MagicMock(spec=...)` whose
    # faked `__class__` slips past that check — would be a test that depends on
    # mock internals to lie about a type. Skipping validation says what is
    # happening out loud.
    result = await AGENT.run(
        AgentContext.model_construct(
            run_id=uuid4(),
            now=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
            dry_run=False,
            db=session,  # type: ignore[arg-type]
        )
    )

    assert result.status != "failed", f"the run failed: {result.errors}"

    bound = [params for _, params in session.calls if params and "since" in params]
    assert bound, "no statement bound a `since` parameter; has the window query moved?"
    for params in bound:
        since = params["since"]
        assert isinstance(since, datetime)
        assert since.tzinfo is None, (
            "`since` is timezone-aware again. `crime_reports.incident_date_time` "
            "is `timestamp without time zone`, and asyncpg raises while binding "
            "an aware datetime to it — which is defect 57, 38 consecutive failed "
            "runs that produced no alert and no empty-output warning. If the "
            "column is ever migrated to `timestamptz`, change it here and delete "
            "this test in the same commit."
        )
