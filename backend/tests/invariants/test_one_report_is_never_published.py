"""
Invariant: **one person's report is never a published claim about a place.**

The user-report counterpart of `test_single_source_never_confirmed.py`, and the
rule this whole sprint turns on. A single report stays its author's private record:
their history, and the input to their GD draft. What reaches a stranger's map is
corroboration — several independent people, same small area, same window.

Four layers enforce it, and this file checks all four, because the layer that is
easiest to add later is the one a future sprint will quietly skip:

1. **`policy/community.status_for`** refuses to issue a status below the threshold,
   and returns `None` rather than a `hidden` state — a cluster that should not be
   published should not exist as a row, because a row is a thing a later query can
   forget to filter.
2. **The `community_clusters_needs_two_reporters` CHECK**, read out of the
   migration. The database will not store the violation.
3. **`to_cluster_statement` raises** rather than producing a sentence for one
   reporter, so there is no way to assemble the text even by hand.
4. **RLS on `crime_reports`** is `auth.uid() = user_id` for SELECT, so a report is
   unreachable by anyone but its author however the client is written.

Layer 4 is the one worth dwelling on. Before this sprint the policy was
`using (true)` and `MapScreen` read every report ever filed, with no bound on time
or space. Tightening the policy is what makes the rest of this more than a
convention: a client bug cannot leak what the database will not return.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from app.policy.community import (
    MIN_REPORTERS_TO_CORROBORATE,
    MIN_REPORTERS_TO_PUBLISH,
    ClusterStatus,
    confidence,
    severity_for,
    status_for,
    to_cluster_statement,
)

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
CLUSTERS_MIGRATION = (
    BACKEND / "migrations" / "versions" / "20261013120100__community_clusters.sql"
)
TRUST_MIGRATION = BACKEND / "migrations" / "versions" / "20261013120000__report_trust.sql"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Layer 1 — the policy refuses
# ---------------------------------------------------------------------------


def test_one_reporter_earns_no_status() -> None:
    assert status_for(0) is None
    assert status_for(1) is None


def test_two_reporters_publish_provisionally() -> None:
    assert status_for(MIN_REPORTERS_TO_PUBLISH) is ClusterStatus.PROVISIONAL


def test_three_reporters_corroborate() -> None:
    assert status_for(MIN_REPORTERS_TO_CORROBORATE) is ClusterStatus.CORROBORATED


def test_the_corroboration_bar_is_above_the_publication_bar() -> None:
    """
    Two tiers mean two thresholds. Collapsing them would make `provisional` dead and
    hand crowd volume the weight reserved for corroborated evidence.
    """
    assert MIN_REPORTERS_TO_CORROBORATE > MIN_REPORTERS_TO_PUBLISH


def test_one_reporter_is_worth_nothing_to_a_decision() -> None:
    assert severity_for(1) == 0.0
    assert severity_for(0) == 0.0


# ---------------------------------------------------------------------------
# Layer 2 — the database refuses
# ---------------------------------------------------------------------------


def test_the_check_constraint_exists() -> None:
    sql = _sql(CLUSTERS_MIGRATION)
    assert "community_clusters_needs_two_reporters" in sql
    assert "check (reporter_count >= 2)" in sql


def test_the_check_matches_the_policy_threshold() -> None:
    """
    The constraint hard-codes 2 and the policy exports it. If someone raises the
    policy threshold without a migration, the database becomes the weaker of the two
    and this says so.
    """
    sql = _sql(CLUSTERS_MIGRATION)
    assert f"check (reporter_count >= {MIN_REPORTERS_TO_PUBLISH})" in sql


def test_corroborated_needs_the_upper_threshold_in_sql_too() -> None:
    sql = _sql(CLUSTERS_MIGRATION)
    assert "community_clusters_corroborated_needs_three" in sql
    assert (
        f"check (status <> 'corroborated' or reporter_count >= "
        f"{MIN_REPORTERS_TO_CORROBORATE})" in sql
    )


def test_reporters_can_never_exceed_reports() -> None:
    """Ten reports from two people is two people; it can never be twelve."""
    sql = _sql(CLUSTERS_MIGRATION)
    assert "community_clusters_reporters_within_reports" in sql
    assert "check (reporter_count <= report_count)" in sql


def test_decay_is_mandatory() -> None:
    """
    No permanent area labels — concept document section 9. A cluster is the object
    most at risk of becoming one, so the CHECK matters more here than on risk_flags.
    """
    sql = _sql(CLUSTERS_MIGRATION)
    assert "community_clusters_half_life_positive" in sql
    assert "check (half_life_hours > 0)" in sql


def test_expiry_is_derived_by_a_trigger_not_by_a_caller() -> None:
    sql = _sql(CLUSTERS_MIGRATION)
    assert "community_clusters_set_expires_at" in sql
    assert "before insert or update of observed_at, severity_0, half_life_hours" in sql


# ---------------------------------------------------------------------------
# Layer 3 — the text cannot be assembled
# ---------------------------------------------------------------------------


def test_a_statement_for_one_reporter_raises() -> None:
    with pytest.raises(ValueError):
        to_cluster_statement(reporter_count=1, radius_m=200, span=timedelta(days=1))


def test_a_statement_names_a_count_and_a_recency_and_nothing_else() -> None:
    statement = to_cluster_statement(
        reporter_count=3, radius_m=200, span=timedelta(days=6)
    )
    assert statement == "3 independent reports within 200 m in the last 6 days."


def test_a_statement_never_characterises_the_place() -> None:
    """
    The whole published vocabulary, checked against the words it must never reach
    for. `to_cluster_statement` runs `framing.assert_mobility_safe`, so this is a
    second opinion on that guard rather than its only enforcement.
    """
    forbidden = (
        "dangerous",
        "unsafe",
        "crime",
        "theft",
        "robbery",
        "assault",
        "harassment",
        "snatching",
        "risky",
        "avoid",
    )
    for reporters in range(MIN_REPORTERS_TO_PUBLISH, 12):
        for days in (1, 3, 14, 60):
            statement = to_cluster_statement(
                reporter_count=reporters, radius_m=200, span=timedelta(days=days)
            )
            lowered = statement.lower()
            for term in forbidden:
                assert term not in lowered, f"{term!r} reached a cluster statement"


def test_a_statement_never_names_a_category_or_family() -> None:
    """
    `family` is the join key and is deliberately not served. A statement that
    mentioned it would be publishing the report category by another name, which is
    the thing `policy/framing.py` refuses for flags.
    """
    statement = to_cluster_statement(
        reporter_count=4, radius_m=200, span=timedelta(days=2)
    )
    for family in ("violent", "property", "other"):
        assert family not in statement.lower()


# ---------------------------------------------------------------------------
# Layer 4 — the reports themselves are private
# ---------------------------------------------------------------------------


def test_reports_are_readable_only_by_their_author() -> None:
    sql = _sql(TRUST_MIGRATION)
    assert 'drop policy if exists "crime_reports_select_all"' in sql, (
        "the old `using (true)` SELECT policy must be dropped, not merely replaced -- "
        "a leftover permissive policy is ORed with the new one"
    )
    assert "for select to authenticated using (auth.uid() = user_id)" in sql


def test_a_client_cannot_write_a_report_status() -> None:
    """
    The self-verify hole. RLS alone cannot close it: the row genuinely belongs to the
    caller. Column privileges can, and they compose with RLS.
    """
    sql = _sql(TRUST_MIGRATION)
    assert "revoke update on public.crime_reports from authenticated" in sql

    grant = sql.split("grant update (", 1)[1].split(") on public.crime_reports", 1)[0]
    assert "status" not in grant, "status must not be in the column-level UPDATE grant"
    assert "user_id" not in grant, "user_id must not be client-writable"
    assert "created_at" not in grant, (
        "created_at must not be client-writable: backdating a report would move it "
        "into a corroboration window it was not in"
    )
    assert "title" in grant, "the content columns should still be editable"


def test_the_verified_column_is_gone() -> None:
    """
    Dropped rather than ignored. A boolean called `verified` left in the schema is an
    invitation to use it again, and this product cannot establish that an incident
    happened.
    """
    sql = _sql(TRUST_MIGRATION)
    assert "drop column if exists verified" in sql


def test_withdrawal_is_the_only_client_route_to_status() -> None:
    sql = _sql(TRUST_MIGRATION)
    assert "create or replace function public.withdraw_crime_report" in sql
    assert "security definer" in sql
    # Pinned search_path: a security definer function that resolves names through
    # the caller's path can be hijacked by a schema the caller controls.
    assert "set search_path = public, pg_temp" in sql
    # Only your own row, only from 'filed'.
    assert "and user_id = auth.uid()" in sql
    assert "and status = 'filed'" in sql


def test_the_status_vocabulary_has_no_trust_level_left() -> None:
    sql = _sql(TRUST_MIGRATION)
    assert "check (status in ('filed', 'withdrawn', 'removed'))" in sql
    for retired in ("'pending'", "'verified'", "'investigating'", "'resolved'"):
        assert f"check (status in ({retired}" not in sql


# ---------------------------------------------------------------------------
# The weights, which are the other half of "published at reduced weight"
# ---------------------------------------------------------------------------


def test_community_evidence_never_reaches_full_confidence() -> None:
    """
    1.0 means independent editors agreed. There is no community-only route to it, at
    any reporter count — which is what keeps the news verification tier meaningful.
    """
    for status in ClusterStatus:
        assert confidence(status) < 1.0


def test_a_provisional_cluster_counts_for_less_than_a_corroborated_one() -> None:
    assert 0.0 < confidence(ClusterStatus.PROVISIONAL) < confidence(
        ClusterStatus.CORROBORATED
    )


def test_a_retired_cluster_counts_for_nothing() -> None:
    assert confidence(ClusterStatus.EXPIRED) == 0.0
    assert confidence(ClusterStatus.REMOVED) == 0.0
    assert confidence("nonsense") == 0.0


def test_a_cluster_cannot_outrank_a_live_fire() -> None:
    """
    The ordering `severity_for`'s cap exists to produce, asserted rather than
    described. A fire's default severity is 70 at confidence 1.0; the worst a
    community cluster can ever contribute is its cap times its best weight.

    If this fails, a pattern of reports is bending routes harder than a road that is
    actually on fire.
    """
    from app.contracts.risk import IncidentKind
    from app.scoring.kinds import KIND_DEFAULTS

    worst_cluster = severity_for(99) * confidence(ClusterStatus.CORROBORATED)
    fire = KIND_DEFAULTS[IncidentKind.FIRE].severity_0 * 1.0
    assert worst_cluster < fire
