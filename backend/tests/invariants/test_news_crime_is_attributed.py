"""
Invariant: **a published crime always names who reported it.**

The third publishing surface says the word "robbery" out loud, which the other two
may not. The whole justification for that is attribution: *The Daily Star reported a
robbery in Pallabi* is a checkable fact about a published article, while *there was
a robbery in Pallabi* is a claim this product has no standing to make and *Pallabi
is dangerous* is the permanent area label the concept document rules out.

So attribution is not a formatting convention here, it is the licence. This file
asserts the three things that keep it true:

1. the guard **rejects** a statement that does not name a publisher, and rejects
   anything that characterises the place or names a group;
2. the only producer of `news_crime_incidents.statement` is
   `app/policy/attribution.py::to_attributed_statement` — checked by reading the
   source, which is crude and is the only check that catches the failure that
   actually happens: someone composing a nicer sentence inside an agent;
3. the database would refuse the violation anyway — the CHECK is quoted here so
   that deleting it from the migration makes this test a visible lie.

The companion invariant is in `test_no_flag_text_bypasses_framing.py`, which
asserts the *opposite* for `risk_flags`: that the crime vocabulary never reaches a
mobility statement. The two tests together are the policy.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.policy.attribution import (
    CATEGORY_NOUNS,
    MAX_STATEMENT_LENGTH,
    MIN_PUBLISHERS_TO_CORROBORATE,
    NEWS_CRIME_HALF_LIFE_HOURS,
    AttributionViolation,
    assert_attribution_safe,
    radius_for,
    severity_for,
    to_attributed_statement,
    weight_for,
)
from app.policy.framing import FramingViolation, assert_mobility_safe

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
APP = BACKEND / "app"
MIGRATION = (
    BACKEND / "migrations" / "versions" / "20261014120000__news_crime_incidents.sql"
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 1. The guard rejects what it must reject
# ---------------------------------------------------------------------------

# One entry per category of thing this surface must not say. If a future change
# makes any of these pass, the invariant is gone — so this list is the test.
REJECTED = [
    # No attribution at all. THE failure this surface exists to prevent.
    "Robbery in Pallabi, 2 days ago",
    "Theft near Gulshan 2",
    "A robbery happened here yesterday",
    # Attributed, but characterising the place.
    "Robbery reported by Prothom Alo in a dangerous area",
    "Theft reported by Jugantor, a notorious hotspot",
    "Assault reported by Samakal — avoid after dark",
    "Robbery reported by Ittefaq in a crime-ridden street",
    # Attributed, but naming a group.
    "Vandalism reported by Prothom Alo at an Awami office",
    "Assault reported by Jugantor on Hindu residents",
    # Attributed, but addressing the reader — advice, not citation.
    "Robbery reported by Prothom Alo; you should avoid this road",
    # A source pasted in rather than cited.
    "Robbery reported by Prothom Alo https://prothomalo.com/x",
]


@pytest.mark.parametrize("statement", REJECTED)
def test_the_guard_rejects_unpublishable_statements(statement: str) -> None:
    with pytest.raises(AttributionViolation):
        assert_attribution_safe(statement)


def test_an_attributed_statement_with_no_judgment_is_accepted() -> None:
    assert_attribution_safe("Robbery reported by Prothom Alo, 2 days ago")
    assert_attribution_safe("Harassment reported by Dhaka Tribune and 2 others, yesterday")


def test_the_missing_publisher_is_reported_as_the_reason() -> None:
    """
    The error has to name the actual problem, because the tempting fix for a
    rejected statement is to delete words until it passes.
    """
    with pytest.raises(AttributionViolation, match="does not name a publisher"):
        assert_attribution_safe("Robbery in Pallabi, 2 days ago")


def test_an_empty_or_overlong_statement_is_refused() -> None:
    with pytest.raises(AttributionViolation):
        assert_attribution_safe("")
    with pytest.raises(AttributionViolation):
        assert_attribution_safe("Robbery reported by Prothom Alo, " + "x" * MAX_STATEMENT_LENGTH)


# ---------------------------------------------------------------------------
# 2. The producer, and the fact that it is the only one
# ---------------------------------------------------------------------------


def test_every_category_produces_a_publishable_statement() -> None:
    """
    Including `other`, which becomes "Incident" rather than "Other crime" — the
    product does not need to assert that an unclassified event was a crime.
    """
    for category in CATEGORY_NOUNS:
        statement = to_attributed_statement(
            category=category,
            publishers=["Prothom Alo"],
            observed_at=NOW - timedelta(days=2),
            now=NOW,
        )
        assert_attribution_safe(statement)
        assert " reported by Prothom Alo" in statement
    assert to_attributed_statement(
        category="other", publishers=["Ittefaq"], observed_at=NOW, now=NOW
    ).startswith("Incident reported by")


def test_the_producer_runs_its_own_output_through_the_guard() -> None:
    """
    The template cannot drift either. An unknown category falls back to `other`
    rather than interpolating whatever string it was handed.
    """
    statement = to_attributed_statement(
        category="definitely-not-a-category",
        publishers=["Prothom Alo"],
        observed_at=NOW,
        now=NOW,
    )
    assert statement.startswith("Incident reported by")


def test_a_statement_cannot_be_produced_with_no_publisher() -> None:
    with pytest.raises(AttributionViolation):
        to_attributed_statement(
            category="robbery", publishers=[], observed_at=NOW, now=NOW
        )
    with pytest.raises(AttributionViolation):
        to_attributed_statement(
            category="robbery", publishers=["", "  "], observed_at=NOW, now=NOW
        )


def test_many_publishers_collapse_rather_than_overflowing_the_cap() -> None:
    statement = to_attributed_statement(
        category="robbery",
        publishers=["Prothom Alo", "Jugantor", "Samakal", "Ittefaq", "Dhaka Tribune"],
        observed_at=NOW,
        now=NOW,
    )
    assert "and 4 others" in statement
    assert len(statement) <= MAX_STATEMENT_LENGTH


def test_the_same_publisher_twice_is_one_publisher() -> None:
    """A follow-up from one outlet is not corroboration, and must not read as it."""
    statement = to_attributed_statement(
        category="robbery",
        publishers=["Prothom Alo", "Prothom Alo"],
        observed_at=NOW,
        now=NOW,
    )
    assert statement == "Robbery reported by Prothom Alo, today"


def test_recency_is_relative_and_never_an_exact_time() -> None:
    for days, expected in ((0, "today"), (1, "yesterday"), (5, "5 days ago")):
        statement = to_attributed_statement(
            category="theft",
            publishers=["Samakal"],
            observed_at=NOW - timedelta(days=days),
            now=NOW,
        )
        assert statement.endswith(expected)


def test_nothing_else_writes_the_statement_column() -> None:
    """
    The crude check, and the one that catches the real failure: a nicer sentence
    composed inside an agent, where no test data would ever reach it.

    Any module that assigns to a dict key or keyword named `statement` while
    writing `news_crime_incidents` must get the value from this one function.

    What counts as an offence is deliberately precise, because the first version of
    this check was not and flagged `statement=row.statement` in the read surface —
    which is a stored value being handed back, not a sentence being made up. The
    thing to catch is **composition**: a literal, an f-string, a concatenation, or a
    call to anything other than the producer. Passing a value through — a bare name,
    or an attribute read off a database row — is not composition and is how the read
    path and the merge path legitimately work.
    """
    producer = APP / "policy" / "attribution.py"
    offenders: list[str] = []

    def composes_text(value: ast.expr) -> bool:
        if isinstance(value, ast.Constant):
            return isinstance(value.value, str)
        if isinstance(value, (ast.JoinedStr, ast.BinOp)):
            return True
        if isinstance(value, ast.Call):
            func = value.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            return name != "to_attributed_statement"
        # ast.Name (a variable) and ast.Attribute (row.statement) pass a value on.
        return False

    for path in APP.rglob("*.py"):
        if path == producer:
            continue
        source = path.read_text(encoding="utf-8")
        if "news_crime_incidents" not in source and "crime_row" not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            # `"statement": <expr>` in a dict literal, or `statement=<expr>`.
            values: list[ast.expr] = []
            if isinstance(node, ast.Dict):
                values += [
                    value
                    for key, value in zip(node.keys, node.values, strict=False)
                    if isinstance(key, ast.Constant) and key.value == "statement"
                ]
            if isinstance(node, ast.Call):
                values += [kw.value for kw in node.keywords if kw.arg == "statement"]
            for value in values:
                if composes_text(value):
                    offenders.append(f"{path.relative_to(BACKEND)}:{value.lineno}")

    assert not offenders, (
        "news_crime_incidents.statement is written outside "
        f"policy/attribution.py::to_attributed_statement at {offenders}. "
        "Attribution is the licence for this surface to use crime vocabulary; a "
        "sentence composed anywhere else is not covered by it."
    )


# ---------------------------------------------------------------------------
# 3. The database refuses the violation too
# ---------------------------------------------------------------------------


def test_the_migration_still_carries_the_attribution_check() -> None:
    """
    Three layers for one rule, as with `risk_flags_confirmed_needs_two_sources`.
    Deleting the CHECK from the migration makes this test fail rather than making
    the surface quietly permissive.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "news_crime_incidents_statement_is_attributed" in sql
    assert "' reported by '" in sql
    assert "news_crime_incidents_statement_length" in sql
    # The radius cap is the other half of "no area labels".
    assert "radius_m > 0 and radius_m <= 1000" in sql


# ---------------------------------------------------------------------------
# 4. The two guards do not overlap — this is the part that is easy to get wrong
# ---------------------------------------------------------------------------


def test_an_attributed_crime_statement_would_still_fail_the_mobility_guard() -> None:
    """
    The surfaces stay separate. If this ever passes, somebody has widened
    `framing.py` to accommodate crime, which is the change the whole three-table
    design exists to avoid.
    """
    statement = to_attributed_statement(
        category="robbery", publishers=["Prothom Alo"], observed_at=NOW, now=NOW
    )
    with pytest.raises(FramingViolation):
        assert_mobility_safe(statement)


def test_naming_a_group_is_banned_on_both_surfaces() -> None:
    """One list, two policies: `framing.NAMED_GROUPS` is shared, never relaxed."""
    offending = "Robbery reported by Awami Media, today"
    with pytest.raises(AttributionViolation):
        assert_attribution_safe(offending)
    with pytest.raises(FramingViolation):
        assert_mobility_safe(offending)


# ---------------------------------------------------------------------------
# 5. Decay and weight — a crime map that never forgets is a judgement
# ---------------------------------------------------------------------------


def test_severity_is_bounded_and_ordered_by_street_risk() -> None:
    for category in CATEGORY_NOUNS:
        assert 0.0 <= severity_for(category) <= 100.0
        assert 0 < radius_for(category) <= 1000
    # A street crime against someone in transit outweighs property crime, which
    # outweighs fraud. This is about how much a ROUTE should move, not about how
    # serious the offence is.
    assert severity_for("robbery") > severity_for("burglary") > severity_for("fraud")
    assert severity_for("harassment") > severity_for("vandalism")


def test_corroboration_raises_the_weight_and_one_source_still_publishes() -> None:
    assert weight_for(1) < weight_for(MIN_PUBLISHERS_TO_CORROBORATE)
    assert 0.0 < weight_for(1) < 1.0


def test_the_half_life_retires_an_incident_in_weeks_not_months() -> None:
    """
    The answer to the obvious objection. Five days of half-life puts a robbery
    below the serve threshold about eighteen days after it was reported, so the map
    forgets — which is what stops it becoming a permanent label on a street.
    """
    assert NEWS_CRIME_HALF_LIFE_HOURS == 120.0
    import math

    # The same formula the database trigger uses: severity 60, threshold 5.
    hours = NEWS_CRIME_HALF_LIFE_HOURS * math.log(60.0 / 5.0) / math.log(2.0)
    assert 14 < hours / 24 < 21
