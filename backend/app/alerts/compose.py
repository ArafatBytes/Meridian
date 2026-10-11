"""
What an alert actually says. B6a / S16.

S16 asks that *"every alert carries its explanation and source count"*, and the
concept document's framing commitment (§9) applies to a notification exactly as
it applies to a map pin — more so, because a notification arrives unasked on a
lock screen and is the one piece of this product a person may read without any
surrounding context.

## The rule this module obeys

**It forwards `flag.mobility_statement` and it composes nothing about any place.**

`app/policy/framing.py::to_mobility_statement` is the only function in the
codebase allowed to produce flag prose, and the invariant test enforces that by
reading the source. That test looks for *assignments to the field*, which this
module never makes — it reads the attribute and puts it in a notification body.
So a well-meant f-string here would slip past it:

    body = f"Road blocked near {flag.place}, take care"   # would NOT be caught

That is a real hole, and `tests/invariants/test_alert_text_is_framed.py` closes
it with a different kind of check: it composes an alert for every combination the
system can produce, deletes the forwarded statement from the body, and asserts
what remains is **byte-identical** across every flag in that category. Fixed
boilerplate plus one forwarded string is the only shape that survives it. Add a
place name, a publisher, a distance that varies, anything derived from the flag
other than the statement and the source count, and the residue differs and the
test fails by name.

That is why the proximity clause below is a constant and not "about 600 m away",
which was the first draft. A distance is honest and would have been genuinely
useful, and it is also per-flag text generated outside `framing.py`. The clause
lost the argument; `data.distance_m` carries the number instead, where the app
can render it without it being prose.

## Why the text is this bland

A lock-screen alert has no room to be careful, so it is built to be unexciting:
a mobility fact, a verification tier, and where to go for more. There is no
severity adjective, no "urgent", no imperative. Severity rode in the body of an
earlier draft as "Severe —" and it is removed: the 0-100 number is in `data`, the
map colours by it, and a word like "severe" on a lock screen is the product
characterising a place, which is the one thing it does not do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from app.alerts.policy import AlertCategory
from app.contracts.risk import RiskFlag
from app.policy.framing import assert_mobility_safe, find_banned_terms

__all__ = [
    "MAX_BODY_LENGTH",
    "PushMessage",
    "compose_alert",
    "compose_test_alert",
    "source_clause",
]

MAX_BODY_LENGTH: Final[int] = 300
"""
Hard cap on the assembled body.

`MAX_STATEMENT_LENGTH` is 160 and the longest fixed suffix this module can add is
about 110 characters, so 300 has headroom without permitting a paragraph. Like
the framing cap it is a content control as much as a layout one: if a future
clause does not fit, the answer is to put it in `data` and let the app render it,
not to raise this number.
"""

# ---------------------------------------------------------------------------
# The fixed strings. This is the entire vocabulary of a Meridian notification.
# ---------------------------------------------------------------------------
# Every one of these is a constant keyed by an enum, never a template with a
# place in it. Adding a sentence here is a deliberate act that shows up in a diff
# and has to survive the invariant test — which is exactly the property
# `framing.py` has, and for the same reason.

_TITLE: Final[dict[AlertCategory, str]] = {
    # No place name in a title. A title is truncated aggressively by both
    # platforms, and a truncated place name is worse than none.
    AlertCategory.CORRIDOR: "On your route now",
    AlertCategory.SCHEDULED: "Expected later today",
    # Not "this area has a history", which labels a place permanently — the thing
    # concept document §9 forbids and demo beat 5 disclaims. The claim is about
    # repetition in the record, and it is phrased as one.
    AlertCategory.CHRONIC: "Reported repeatedly here",
    AlertCategory.TEST: "Meridian test alert",
}

_CONFIRMED_CLAUSE: Final[str] = "Confirmed by {n} independent sources."
_SINGLE_SOURCE_CLAUSE: Final[str] = "Unconfirmed — a single source so far."

_PROXIMITY: Final[dict[AlertCategory, str]] = {
    # The "explanation" S16 asks for: why this arrived. It also states the
    # product's current limit out loud, because the honest answer to "why am I
    # getting this here?" is that the app knows where you were when you last
    # opened it — background location is S17 and is not built.
    AlertCategory.CORRIDOR: "Near where the app last had your location.",
    AlertCategory.SCHEDULED: "Near where the app last had your location. Not started yet.",
    AlertCategory.CHRONIC: "A historical pattern, not something happening now.",
    AlertCategory.TEST: "You asked for this from Settings, to check delivery works.",
}

_TEST_BODY: Final[str] = (
    "Push delivery is working. This is the only notification Meridian will ever "
    "send that is not about a real road."
)


class AlertCompositionError(RuntimeError):
    """
    Raised when the assembled text fails its own guard.

    An exception rather than a truncation or a fallback string. A notification is
    the most public thing this system emits; sending a half-sanitised one is
    worse than sending none, and the dispatcher records the failure against the
    run so it is visible rather than silently skipped.
    """


@dataclass(frozen=True, slots=True)
class PushMessage:
    """
    One notification, ready for the transport.

    `data` is the structured half and is where everything the body deliberately
    does not say ends up: the flag id so a tap can open the right sheet, the
    severity the map colours by, the distance, the source count as a number. The
    app renders those; the body only ever carries the forwarded statement and
    fixed boilerplate.
    """

    title: str
    body: str
    category: AlertCategory
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def channel_id(self) -> str:
        """
        The Android channel. Must match a channel the app has created, or Android
        files the notification under a default channel with no sound.

        `NOTIFICATION_CHANNELS` in `frontend/src/constants/app.constants.ts` is
        the other half of this, and `test_channel_ids_match_the_client` reads that
        file to assert the two agree — a mismatch is silent on both sides and
        shows up only as a notification that arrives without the importance it
        was supposed to have.
        """
        return "risk_alert" if self.category != AlertCategory.TEST else "system"


def source_clause(*, status: str, source_count: int) -> str:
    """
    The verification tier, in words.

    D05 made the confirmed/unconfirmed distinction visible on the map as fill and
    ring style. A notification has no shape to vary, so it says it. The tiering is
    an ethical commitment and a lock screen is the place it matters most: this may
    be the only sentence about the event anyone reads.

    `source_count` is only stated when it is corroborated. "1 source" invites the
    reader to weigh a number; "unconfirmed" tells them the thing that matters.
    """
    if status == "confirmed":
        return _CONFIRMED_CLAUSE.format(n=source_count)
    return _SINGLE_SOURCE_CLAUSE


def _guard(title: str, body: str) -> None:
    """
    The composed text has to pass the same guard its parts did.

    `assert_mobility_safe` is not reused wholesale for the body: it caps at
    `MAX_STATEMENT_LENGTH` (160), and a body is a statement plus two fixed
    clauses, so it legitimately exceeds that. What carries over is the part that
    is about meaning rather than length — the banned vocabulary — plus this
    module's own cap.

    The title is checked too. It is a constant from `_TITLE`, so this can only
    fire if somebody edits that table badly, which is precisely when a check is
    worth having.
    """
    if len(body) > MAX_BODY_LENGTH:
        raise AlertCompositionError(
            f"alert body is {len(body)} characters; the limit is {MAX_BODY_LENGTH}. "
            "Move the detail into `data` rather than raising the limit."
        )
    for label, text in (("title", title), ("body", body)):
        banned = find_banned_terms(text)
        if banned:
            raise AlertCompositionError(
                f"alert {label} uses non-mobility vocabulary: "
                + ", ".join(repr(t) for t in banned)
                + ". Describe the effect on movement, not the event or the people."
            )


def compose_alert(
    *,
    flag: RiskFlag,
    category: AlertCategory,
    severity: float,
    distance_m: int | None = None,
) -> PushMessage:
    """
    The notification for one flag.

    `severity` is passed in rather than read off the flag because the decision
    used `effective_severity` — decayed and damped by confidence — and the history
    row must record the number the decision actually used. Re-deriving it here
    would risk the two drifting.

    The statement is re-guarded on the way out even though `framing.py` already
    guarded it when it was written. It has been through the database since then,
    and a row edited by hand in the Supabase console is a real thing that happens
    on this project.
    """
    statement = flag.mobility_statement
    assert_mobility_safe(statement)

    title = _TITLE[category]
    body = " ".join(
        (
            statement,
            source_clause(status=flag.status, source_count=flag.source_count),
            _PROXIMITY[category],
        )
    )
    _guard(title, body)

    data: dict[str, Any] = {
        "type": "risk_alert",
        "category": category.value,
        "flagId": str(flag.flag_id),
        "lat": flag.lat,
        "lon": flag.lon,
        "radiusM": flag.radius_m,
        "severity": round(severity, 1),
        "status": flag.status,
        "sourceCount": flag.source_count,
        "kind": flag.kind.value,
    }
    if distance_m is not None:
        data["distanceM"] = distance_m
    if flag.valid_from is not None:
        data["validFrom"] = flag.valid_from.isoformat()

    return PushMessage(title=title, body=body, category=category, data=data)


def compose_test_alert() -> PushMessage:
    """
    The notification `POST /notifications/test` sends.

    It exists so the device walkthrough can prove the delivery path — permissions,
    token, Expo credentials, channel — without waiting for Dhaka to produce an
    incident. It is deliberately unmistakable: a real alert never says "test", and
    nobody should ever have to wonder which kind they are holding.
    """
    # `" ".join` rather than an f-string, and the reason is a test rather than
    # taste: `test_compose_py_contains_no_f_strings` forbids them in this module,
    # because an f-string is how per-place prose gets written. Both operands here
    # are constants, so the f-string was harmless — and exempting it would have
    # left the next one, which would not be, with a precedent to point at.
    message = PushMessage(
        title=_TITLE[AlertCategory.TEST],
        body=" ".join((_TEST_BODY, _PROXIMITY[AlertCategory.TEST])),
        category=AlertCategory.TEST,
        data={"type": "test"},
    )
    _guard(message.title, message.body)
    return message
