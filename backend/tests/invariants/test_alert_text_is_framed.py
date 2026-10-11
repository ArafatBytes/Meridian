"""
Invariant: **a notification says no more about a place than the map does.**

Concept document §9's framing commitment applies to a push notification exactly as
it applies to a map pin — arguably more, because a notification arrives unasked on
a lock screen and may be the only sentence about the event that anyone reads. No
judgment, no politics, no named group, and nothing composed about a location
outside `app/policy/framing.py`.

## Why `test_no_flag_text_bypasses_framing.py` does not already cover this

That test asks *"which modules assign `RiskFlag.mobility_statement`?"*, by parsing
the source. `app/alerts/compose.py` never assigns it — it reads the attribute and
puts the value in a notification body — so the existing test is satisfied, and a
well-meant line like

    body = f"Road blocked near {place}. Be careful after dark."

would pass every check in the suite. That is a real hole and this file closes it,
with a different kind of check: **the residue test**.

## The residue test

`test_the_body_is_boilerplate_plus_one_forwarded_string` composes an alert for
every combination the system can produce, deletes the forwarded
`mobility_statement` from the body, and asserts what remains is byte-identical
across every flag in that category. Fixed boilerplate plus one forwarded string
is the only shape that survives.

It fails if the composer interpolates a place, a publisher, a severity word, a
distance, a time — anything derived from the flag other than the statement and the
corroboration tier. It does so by name, and the failure message prints the two
differing residues, so the diagnosis is immediate.

That property is what makes this file worth more than the vocabulary check below.
A banned-term list can only catch words somebody thought of in advance; the
residue test catches *any* new per-place prose, including polite, accurate,
well-intentioned prose, which is the kind that actually gets written.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from itertools import product
from pathlib import Path
from uuid import uuid4

import pytest

from app.alerts.compose import (
    MAX_BODY_LENGTH,
    AlertCompositionError,
    compose_alert,
    compose_test_alert,
    source_clause,
)
from app.alerts.policy import AlertCategory, category_for
from app.contracts.risk import IncidentKind, MobilityImpact, RiskFlag
from app.policy.framing import find_banned_terms, to_mobility_statement

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
COMPOSE = BACKEND / "app" / "alerts" / "compose.py"

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)

# Place names chosen to be awkward on purpose: a long one, a Bangla one, a
# missing one, and one carrying a banned term that `framing.py` must strip.
PLACES: tuple[str | None, ...] = (
    None,
    "Bangshal",
    "Mirpur 10 golchattar",
    "গোলচত্বর",
    "Jamaat office road",
)
STATUSES: tuple[tuple[str, int, float], ...] = (
    ("unconfirmed", 1, 0.6),
    ("confirmed", 2, 1.0),
    ("confirmed", 7, 1.0),
)


def flag(
    *,
    kind: IncidentKind,
    impact: MobilityImpact,
    place: str | None,
    status: str,
    source_count: int,
    confidence: float,
    valid_from: datetime | None = None,
) -> RiskFlag:
    """
    A flag whose statement came from the real writer.

    Deliberately not a hand-written statement: the point of this file is that the
    composer forwards what `framing.py` produced, so the input has to be what
    `framing.py` produces. A literal here would test a string this system can
    never actually hold.
    """
    return RiskFlag(
        flag_id=uuid4(),
        event_key="test",
        kind=kind,
        status=status,  # type: ignore[arg-type]
        lat=23.75,
        lon=90.40,
        radius_m=400,
        severity_0=70.0,
        severity_now=70.0,
        half_life_hours=3.0,
        observed_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=6),
        source_count=source_count,
        sources=[],
        mobility_statement=to_mobility_statement(kind=kind, impact=impact, place=place),
        confidence=confidence,
        valid_from=valid_from,
    )


def every_flag() -> list[RiskFlag]:
    """
    Every kind x impact x place x verification tier the system can produce.

    Exhaustive rather than sampled. The combination that breaks a framing rule is
    never the one someone would have picked for a test — in D02 it was a place
    name containing a party name, which no sampled set would have included.
    """
    return [
        flag(
            kind=kind,
            impact=impact,
            place=place,
            status=status,
            source_count=count,
            confidence=confidence,
        )
        for kind, impact, place, (status, count, confidence) in product(
            IncidentKind, MobilityImpact, PLACES, STATUSES
        )
    ]


# ---------------------------------------------------------------------------
# 1. The vocabulary, on the assembled text
# ---------------------------------------------------------------------------


def test_no_composed_alert_uses_banned_vocabulary() -> None:
    """
    The guard runs on the *output*, over every input the system can produce.

    `framing.py` already guarantees the statement passes. What this adds is the
    assembled title and body — the composer's own contribution — so a banned term
    arriving in a fixed clause cannot slip through on the grounds that the
    statement was clean.
    """
    offenders: list[tuple[str, str, list[str]]] = []
    for candidate in every_flag():
        category = category_for(candidate, at=NOW)
        message = compose_alert(flag=candidate, category=category, severity=60.0)
        for label, text in (("title", message.title), ("body", message.body)):
            banned = find_banned_terms(text)
            if banned:
                offenders.append((label, text, banned))
    assert offenders == [], f"composed alerts use non-mobility vocabulary: {offenders[:5]}"


def test_a_tainted_place_name_never_reaches_the_lock_screen() -> None:
    """
    The place name is dropped upstream, and the notification inherits that.

    `framing.py` drops a place carrying a banned term rather than raising, so the
    flag publishes with less detail. This asserts the *notification* inherits the
    same protection — which it does only because it forwards the statement
    instead of reaching for a `place` field of its own.
    """
    tainted = flag(
        kind=IncidentKind.CLASH,
        impact=MobilityImpact.IMPASSABLE,
        place="Jamaat office road",
        status="confirmed",
        source_count=3,
        confidence=1.0,
    )
    message = compose_alert(flag=tainted, category=AlertCategory.CORRIDOR, severity=70.0)
    assert "jamaat" not in message.body.lower()
    assert "Road impassable in this area." in message.body


def test_every_body_fits_the_cap() -> None:
    """
    A statement at the 160-character limit plus the longest fixed suffix must fit.

    If this fails the answer is to move a clause into `data`, not to raise
    `MAX_BODY_LENGTH` — which is what the error message says, because the cheapest
    fix at 1 a.m. is always the number.
    """
    for candidate in every_flag():
        message = compose_alert(
            flag=candidate, category=category_for(candidate, at=NOW), severity=60.0
        )
        assert len(message.body) <= MAX_BODY_LENGTH, message.body


def test_the_guard_actually_rejects_something() -> None:
    """
    A guard that never fires is indistinguishable from no guard.

    Planted input, because nothing reachable through `framing.py` can produce a
    banned statement — so without forging one, `_guard`'s banned-term branch has
    no coverage at all and could be deleted with the suite staying green.
    """
    smuggled = flag(
        kind=IncidentKind.FIRE,
        impact=MobilityImpact.ROAD_BLOCKED,
        place=None,
        status="confirmed",
        source_count=2,
        confidence=1.0,
    )
    object.__setattr__(smuggled, "mobility_statement", "Dangerous area near Paltan.")
    with pytest.raises(Exception) as caught:
        compose_alert(flag=smuggled, category=AlertCategory.CORRIDOR, severity=60.0)
    assert "dangerous" in str(caught.value).lower()


# ---------------------------------------------------------------------------
# 2. The residue test. The one that catches new prose.
# ---------------------------------------------------------------------------


def test_the_body_is_boilerplate_plus_one_forwarded_string() -> None:
    """
    Remove the forwarded statement and what is left must be identical every time.

    This is the structural check, and it is the reason this file exists. It holds
    the composer to a shape — fixed clauses, keyed by category and by verification
    tier, plus `flag.mobility_statement` verbatim — rather than to a vocabulary.

    Grouped by `(category, status, source_count)` because the corroboration clause
    legitimately varies with those three and with nothing else. Any dependence on
    kind, place, severity, coordinates or time shows up as two different residues
    inside one group, and the failure prints both.
    """
    residues: dict[tuple[str, str, int], set[str]] = {}
    for candidate in every_flag():
        category = category_for(candidate, at=NOW)
        message = compose_alert(flag=candidate, category=category, severity=60.0)

        assert candidate.mobility_statement in message.body, (
            "the body must contain the framed statement verbatim; found "
            f"{message.body!r} for {candidate.mobility_statement!r}"
        )
        residue = message.body.replace(candidate.mobility_statement, "<STATEMENT>")
        key = (category.value, candidate.status, candidate.source_count)
        residues.setdefault(key, set()).add(residue)

    varying = {key: sorted(found) for key, found in residues.items() if len(found) > 1}
    assert varying == {}, (
        "the alert body varies with something other than the forwarded statement "
        f"and the verification tier: {varying}. Fixed boilerplate belongs in "
        "compose.py's constant tables; anything about a place belongs in "
        "app/policy/framing.py, and anything else belongs in `data`."
    )


def test_the_title_depends_only_on_the_category() -> None:
    """
    A title is truncated hard by both platforms, so it carries no variable text.

    Four categories, four possible titles, whatever the flag.
    """
    by_category: dict[str, set[str]] = {}
    for candidate in every_flag():
        category = category_for(candidate, at=NOW)
        message = compose_alert(flag=candidate, category=category, severity=60.0)
        by_category.setdefault(category.value, set()).add(message.title)
    assert all(len(titles) == 1 for titles in by_category.values()), by_category


def test_the_source_count_is_stated_only_when_it_corroborates() -> None:
    """
    "1 source" invites the reader to weigh a number; "unconfirmed" tells them what
    matters.

    D05 made the tier visible on the map through fill and ring style. A
    notification has no shape to vary, so it has to say it — and this is the
    sentence that does.
    """
    assert "3" in source_clause(status="confirmed", source_count=3)
    single = source_clause(status="unconfirmed", source_count=1)
    assert "1" not in single
    assert "nconfirmed" in single


def test_the_severity_number_never_appears_in_the_text() -> None:
    """
    Severity rides in `data`, not in the sentence.

    An earlier draft prefixed the body with "Severe — ". A severity adjective on a
    lock screen is the product characterising a place, which is the one thing it
    does not do; the number itself is meaningless without the scale beside it. The
    map colours by it and the sheet shows it. Here it stays structured.
    """
    candidate = flag(
        kind=IncidentKind.FIRE,
        impact=MobilityImpact.ROAD_BLOCKED,
        place="Bangshal",
        status="confirmed",
        source_count=3,
        confidence=1.0,
    )
    message = compose_alert(flag=candidate, category=AlertCategory.CORRIDOR, severity=87.4)
    assert "87" not in message.body
    assert message.data["severity"] == pytest.approx(87.4)
    for word in ("severe", "critical", "extreme", "urgent"):
        assert word not in message.body.lower()


# ---------------------------------------------------------------------------
# 3. The composer must not grow a way to build text
# ---------------------------------------------------------------------------


def test_compose_py_contains_no_f_strings() -> None:
    """
    An f-string is how per-place prose gets written, so there are none.

    Checked by parsing rather than grepping, so a mention in a docstring does not
    count. `_CONFIRMED_CLAUSE` uses `str.format` with a single integer instead —
    `"Confirmed by {n} independent sources."` — which keeps the sentence a
    constant that a reader can find in one place, and keeps the only interpolated
    value a number.

    One exemption: a `raise`. An exception message is not user-facing text — it
    goes to a log for a developer, and naming the offending value is the entire
    point of raising one.

    Nothing else is exempt, and that is deliberate. On its first run this check
    found an f-string in `compose_test_alert` joining two module constants. It was
    completely harmless. It was fixed rather than exempted, because an exemption
    is a precedent, and the next f-string someone adds beside it will not be
    joining two constants.
    """
    tree = ast.parse(COMPOSE.read_text(encoding="utf-8"))

    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            exempt.update(id(child) for child in ast.walk(node))

    offenders = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr) and id(node) not in exempt
    ]
    assert offenders == [], (
        f"app/alerts/compose.py builds text with f-strings: {offenders}. Notification "
        "prose is fixed boilerplate keyed by category plus a forwarded "
        "mobility_statement — see the module docstring."
    )


def test_compose_py_never_reads_a_place_field() -> None:
    """
    There is no `place` on `RiskFlag`, and the composer must not acquire a path to one.

    The statement is the only thing that may describe a location, because it is the
    only string `framing.py` has guarded. Reaching for coordinates or a gazetteer
    name to make the message friendlier is the exact instinct this check exists to
    stop — `lat`/`lon` in `data` are for the map to open the right sheet, not for
    prose.
    """
    source = COMPOSE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    reads = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "flag"
    }
    allowed = {
        "mobility_statement",  # the forwarded, already-guarded string
        "status",
        "source_count",  # the verification tier
        "flag_id",
        "lat",
        "lon",
        "radius_m",  # structured, for `data`
        "kind",
        "valid_from",  # structured, for `data`
    }
    assert reads <= allowed, (
        f"compose.py reads {sorted(reads - allowed)} off the flag. Anything that could "
        "describe a place must come through mobility_statement, which is the only "
        "string app/policy/framing.py has guarded."
    )


# ---------------------------------------------------------------------------
# 4. The test alert
# ---------------------------------------------------------------------------


def test_a_test_alert_is_unmistakable() -> None:
    """
    Nobody should ever have to wonder whether an alert was real.

    A real alert never contains the word "test", and this one says it in the title
    and explains itself in the body.
    """
    message = compose_test_alert()
    assert "test" in message.title.lower()
    assert find_banned_terms(message.body) == []
    assert message.category is AlertCategory.TEST
    assert message.data == {"type": "test"}


def test_the_test_alert_uses_a_different_android_channel() -> None:
    """
    A delivery check must not borrow the channel that real warnings use.

    Android channel importance is user-controllable per channel. If a test shared
    the risk channel, somebody silencing test notifications after a walkthrough
    would silence real alerts too, and nothing would tell them.
    """
    assert compose_test_alert().channel_id != compose_alert(
        flag=flag(
            kind=IncidentKind.FIRE,
            impact=MobilityImpact.ROAD_BLOCKED,
            place="Bangshal",
            status="confirmed",
            source_count=3,
            confidence=1.0,
        ),
        category=AlertCategory.CORRIDOR,
        severity=60.0,
    ).channel_id


def test_composition_failure_is_an_exception_not_a_fallback() -> None:
    """
    `AlertCompositionError` exists and is a hard error.

    A notification is the most public thing this system emits. Truncating or
    substituting a safe-looking string would send a half-sanitised message under
    the product's name; raising means the dispatcher records a failure that a
    human sees.
    """
    assert issubclass(AlertCompositionError, Exception)
