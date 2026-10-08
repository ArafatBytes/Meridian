"""
Invariant: **mobility framing, never judgment.**

Concept document §9. Gatherings and processions surface as "road blocked", "heavy
crowd", "expect delay" — never as safety or political characterisations, and never
naming a group, party, religion or ethnicity.

IMPLEMENTATION_PLAN.md §4 asks this test to assert two things, and it asserts
both:

1. every `mobility_statement` that can reach a user passes the guard;
2. no module other than `app/policy/framing.py` writes that field.

The second is checked by reading the source, which is crude. It is also the only
check that catches the failure that actually happens — someone building a nice
descriptive sentence inside an agent, where no test data would ever reach it.
"""

import ast
import json
from pathlib import Path

import pytest

from app.contracts.risk import IncidentKind, MobilityImpact
from app.policy.framing import (
    BANNED_TERMS,
    MAX_STATEMENT_LENGTH,
    FramingViolation,
    assert_mobility_safe,
    find_banned_terms,
    to_mobility_statement,
)

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
APP = BACKEND / "app"
FIXTURE = BACKEND / "data" / "fixtures" / "risk_flags.json"


# ---------------------------------------------------------------------------
# 1. The guard rejects what it must reject
# ---------------------------------------------------------------------------

# One entry per category of thing the product must not say. If a future change
# makes any of these pass, the invariant is gone — so this list is the test.
REJECTED = [
    # Safety characterisation
    "Dangerous area, avoid after dark.",
    "This road is unsafe.",
    # Crime and violence
    "Robbery reported near Gulshan 2.",
    "Violent attack near New Market.",
    "Mob gathered near Paltan.",
    # Events named by their politics
    "Hartal near Motijheel.",
    "Protest blocking Shahbagh.",
    "Clash near Paltan.",
    "Procession near Bangshal.",
    # Named groups
    "BNP rally blocking the road.",
    "Awami League march near Paltan.",
    "Jamaat gathering near Baitul Mukarram.",
    "Hindu community gathering near Dhakeshwari.",
    # Bangla
    "মিরপুরে সংঘর্ষ, রাস্তা বন্ধ।",
    "হরতালের কারণে যানজট।",
    "বিপজ্জনক এলাকা।",
]


@pytest.mark.parametrize("statement", REJECTED)
def test_guard_rejects_non_mobility_vocabulary(statement: str) -> None:
    with pytest.raises(FramingViolation):
        assert_mobility_safe(statement)


def test_guard_rejects_empty_and_overlong() -> None:
    for bad in ["", "   ", "x" * (MAX_STATEMENT_LENGTH + 1)]:
        with pytest.raises(FramingViolation):
            assert_mobility_safe(bad)


def test_guard_rejects_a_pasted_url() -> None:
    """Sources belong in `RiskFlag.sources`, not inside the sentence."""
    with pytest.raises(FramingViolation):
        assert_mobility_safe("Road blocked near Bangshal https://example.com/story")


def test_guard_accepts_ordinary_place_names_that_merely_look_suspicious() -> None:
    """
    A guard that fires on innocent text gets switched off, and then the invariant
    is gone for a reason nobody wrote down.

    "Mobile" contains "mob"; "Mobarak" does too; "Rapeseed" contains "rape". All
    three are the kind of false positive that would have someone reaching for a
    way around the guard within a week. Letter-boundary matching is what prevents
    them, and these cases pin that behaviour.
    """
    assert find_banned_terms("Lane closed near Mobarak Road, delay likely.") == []
    assert find_banned_terms("Heavy crowd near Mobile Market.") == []
    assert find_banned_terms("Delay likely near Rapeseed Lane.") == []


# ---------------------------------------------------------------------------
# 2. Everything the writer produces passes the guard
# ---------------------------------------------------------------------------


def test_every_template_combination_is_safe() -> None:
    """
    All kinds x all impacts, with and without a place name.

    This is what stops the templates drifting: the guard runs on the writer's own
    output, so there is no way to add a banned word to a template and have the
    suite stay green.
    """
    for kind in IncidentKind:
        for impact in MobilityImpact:
            for place in (None, "Mirpur 10 golchattar", "Bangshal", "গোলচত্বর"):
                assert_mobility_safe(to_mobility_statement(kind=kind, impact=impact, place=place))


def test_a_tainted_place_name_is_dropped_not_published() -> None:
    """
    A place name carrying a banned term must not reach the user, and must not
    destroy the flag either.

    The news will eventually hand us a location like "Jamaat office road". Raising
    would lose a genuine mobility warning; passing it through would break the
    invariant. Dropping the place name is the third option.
    """
    statement = to_mobility_statement(
        kind=IncidentKind.CLASH,
        impact=MobilityImpact.IMPASSABLE,
        place="Jamaat office road",
    )
    assert_mobility_safe(statement)
    assert "jamaat" not in statement.lower()
    assert statement == "Road impassable in this area."


def test_a_clash_is_published_as_a_blocked_road() -> None:
    """The headline case from concept document §9, pinned as an example."""
    assert (
        to_mobility_statement(
            kind=IncidentKind.CLASH, impact=MobilityImpact.ROAD_BLOCKED, place="Paltan"
        )
        == "Road blocked near Paltan."
    )
    assert (
        to_mobility_statement(
            kind=IncidentKind.PROCESSION, impact=MobilityImpact.HEAVY_CROWD, place="Shahbagh"
        )
        == "Heavy crowd near Shahbagh."
    )


# ---------------------------------------------------------------------------
# 3. The fixture contains no prose
# ---------------------------------------------------------------------------


def test_fixture_declares_no_mobility_statement() -> None:
    """
    `data/fixtures/risk_flags.json` must hold structured fields only.

    A fixture with hand-written flag text would be text that never passed the
    guard, sitting in the demo database, indistinguishable from text that did.
    ~200 rows arrive in D02, which is 200 chances to smuggle one in.
    """
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    offenders = [f["event_key"] for f in data["flags"] if "mobility_statement" in f]
    assert offenders == [], (
        "these fixture entries contain hand-written flag text: "
        f"{offenders}. Set 'mobility_impact' and 'place' instead; framing.py writes "
        "the sentence."
    )


def test_every_fixture_entry_produces_safe_text() -> None:
    """Run the fixture through the writer and guard the result, as the seeder does."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["flags"], "the fixture is empty"
    for entry in data["flags"]:
        statement = to_mobility_statement(
            kind=IncidentKind(entry["kind"]),
            impact=MobilityImpact(entry["mobility_impact"]),
            place=entry.get("place"),
        )
        assert_mobility_safe(statement)


# ---------------------------------------------------------------------------
# 4. Nothing else writes the field
# ---------------------------------------------------------------------------

# Modules allowed to mention `mobility_statement` as an assignment target, each
# with the reason. Anything else is a new writer and has to be justified by
# editing this list, which is the point: it turns an invisible drift into a
# visible diff.
ALLOWED_WRITERS: dict[str, str] = {
    "app/policy/framing.py": "the sole writer",
    "app/contracts/risk.py": "declares the field",
    "app/scoring/surface_db.py": "rehydrates a stored row; reading, not writing",
    "app/scoring/surface_seeded.py": "rehydrates a fixture row; reading, not writing",
    "app/scoring/fixture.py": "calls to_mobility_statement() for every fixture row",
    "app/scoring/chronic.py": "calls to_mobility_statement() for every chronic row",
    "app/agents/live_risk.py": "calls to_mobility_statement() for every published news flag",
}


def _assignments_to_mobility_statement(path: Path) -> bool:
    """
    Whether this module assigns `mobility_statement` anywhere.

    Parsed rather than grepped, so a mention in a docstring or a comment does not
    count. Covers keyword arguments (`RiskFlag(mobility_statement=...)`), plain
    assignment, attribute assignment (`flag.mobility_statement = ...`), **and a
    string key in a dict literal** (`{"mobility_statement": ...}`), which together are
    every way the field can actually be set.

    The dict-literal case was added in D02 and it was a real blind spot, not a
    formality. `app/scoring/fixture.py` builds insert-shaped dicts rather than
    `RiskFlag` objects — a flag has no `flag_id` until the database has seen it — so
    before D02 the only producers of this field outside `framing.py` lived in
    `scripts/`, which this test does not scan. A hand-written statement in a dict
    literal under `app/` would have gone straight past it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "mobility_statement":
            return True
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "mobility_statement":
                    return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "mobility_statement":
                    return True
                if isinstance(target, ast.Attribute) and target.attr == "mobility_statement":
                    return True
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "mobility_statement":
                return True
            if isinstance(target, ast.Attribute) and target.attr == "mobility_statement":
                return True
    return False


def test_only_framing_writes_mobility_statement() -> None:
    writers = sorted(
        str(path.relative_to(BACKEND)).replace("\\", "/")
        for path in APP.rglob("*.py")
        if _assignments_to_mobility_statement(path)
    )
    unexpected = [w for w in writers if w not in ALLOWED_WRITERS]
    assert unexpected == [], (
        f"{unexpected} write RiskFlag.mobility_statement. Flag text comes from "
        "app/policy/framing.py::to_mobility_statement() and nowhere else "
        "(concept document §9). If one of these genuinely only rehydrates a stored "
        "row, add it to ALLOWED_WRITERS with that reason."
    )


def test_allowed_writers_all_still_exist() -> None:
    """
    A renamed file would silently shrink the allowlist and make the test above
    weaker rather than failing. Catch that directly.
    """
    missing = [name for name in ALLOWED_WRITERS if not (BACKEND / name).is_file()]
    assert missing == [], f"ALLOWED_WRITERS names files that no longer exist: {missing}"


def test_banned_list_is_not_empty() -> None:
    """
    A guard with an empty list passes everything.

    Trivial, and it is exactly the shape the invariant would fail in: someone
    comments out a group while debugging and every other test still goes green.
    """
    assert len(BANNED_TERMS) > 50
    for required in ("dangerous", "hartal", "clash", "bnp", "awami"):
        assert required in BANNED_TERMS, f"{required!r} fell out of the banned list"
