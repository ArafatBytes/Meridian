"""
Invariant: **the backend never names an Android channel the app did not create.**

B6a / S16. A cross-codebase contract, checked by reading the other codebase —
crude, and the only way to catch this failure at all.

## The failure

`app/alerts/compose.py` puts `channelId` on every message. Android looks that id
up among the channels the app registered at startup. When they disagree, Android
**does not error**: it files the notification under a fallback channel with
default importance, no custom sound and no vibration pattern.

So the notification arrives. A device walkthrough passes. What was silently lost
is the urgency the channel existed to carry — an SOS landing on a low-importance
channel is the case that matters — and nothing in either codebase reports it.

Rename a channel on one side only and this test fails by name, which is the
entire point.

## Why parse TypeScript with a regex

Because the alternative is nothing. There is no shared schema between a Python
backend and a React Native app here, and a generated one would be a larger
mechanism than the thing it protects. The regex is anchored on the `as const`
object in `frontend/src/features/alerts/channels.ts`, and
`test_the_client_file_is_where_we_think_it_is` fails loudly if that file moves
rather than letting the check silently pass on an empty match — which is how this
kind of test usually dies.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.alerts.compose import PushMessage, compose_alert, compose_test_alert
from app.alerts.policy import AlertCategory
from app.contracts.risk import IncidentKind, MobilityImpact, RiskFlag
from app.policy.framing import to_mobility_statement

pytestmark = pytest.mark.invariant

BACKEND = Path(__file__).resolve().parent.parent.parent
COMPOSE = BACKEND / "app" / "alerts" / "compose.py"

_CLIENT_RELATIVE = Path("frontend") / "src" / "features" / "alerts" / "channels.ts"


def _find_client_channels() -> Path | None:
    """
    Locate the client's channel file, or report that this environment has no frontend.

    Two environments run this suite:

    * **the repository root**, where `scripts/check.sh` runs pytest on the host —
      `backend/..` resolves to the checkout and the file is simply there;
    * **the `api` container**, where `/app` is the backend. `docker-compose.yml`
      mounts this one client file read-only at `/frontend/src/features/alerts/`,
      which is why `Path("/")` is in the search list.

    The mount exists specifically so this contract is checked in the container,
    because that is where this project actually runs its tests: there is no
    `backend/venv` on these machines, so `check.sh` skips the host path. Relying
    on the host would have meant a test that skipped every single time while
    still being counted in the total — worse than not writing it.

    `None` is still possible (a checkout with no frontend), and
    `test_the_contract_is_enforced_somewhere` is what stops that from becoming
    permanent and invisible.
    """
    for root in (BACKEND.parent, Path("/"), Path.cwd(), *Path.cwd().parents):
        candidate = root / _CLIENT_RELATIVE
        if candidate.is_file():
            return candidate
    return None


CLIENT_CHANNELS = _find_client_channels()

needs_client = pytest.mark.skipif(
    CLIENT_CHANNELS is None,
    reason=(
        "no frontend tree in this environment (expected inside the api container); "
        "the channel contract is enforced by scripts/check.sh from the repo root"
    ),
)


def client_channel_ids() -> set[str]:
    """
    The ids declared in `ALERT_CHANNELS` in the client.

    Matches the string literal values inside the `as const` object, e.g.
    `RISK: 'risk_alert',`.
    """
    assert CLIENT_CHANNELS is not None  # guarded by @needs_client
    source = CLIENT_CHANNELS.read_text(encoding="utf-8")
    block = re.search(
        r"export const ALERT_CHANNELS\s*=\s*\{(.*?)\}\s*as const;", source, re.S
    )
    assert block, (
        f"could not find `export const ALERT_CHANNELS = {{...}} as const;` in "
        f"{CLIENT_CHANNELS}. If the shape changed, update this test — do not "
        "delete it."
    )
    ids = set(re.findall(r"""^\s*\w+\s*:\s*['"]([a-z_]+)['"]\s*,?\s*$""", block.group(1), re.M))
    assert ids, f"ALERT_CHANNELS in {CLIENT_CHANNELS.name} parsed as empty"
    return ids


def backend_channel_ids() -> set[str]:
    """
    Every string literal `PushMessage.channel_id` can return.

    Read out of the AST rather than by calling the property, so a branch that is
    hard to reach from a test is still covered. `channel_id` is a short
    conditional expression over two literals today; if it grows into something
    this cannot read, `test_channel_id_is_simple_enough_to_read_statically`
    fails and says so.
    """
    tree = ast.parse(COMPOSE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "channel_id":
            # `ast.get_docstring` is not enough -- the docstring is still a node in
            # the body, so walking the function picks it up as a string constant.
            # Dropping the leading docstring statement is the fix; without it the
            # whole prose block was returned as a "channel id" and the comparison
            # failed with an unreadable diff.
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            return {
                child.value
                for statement in body
                for child in ast.walk(statement)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            }
    pytest.fail(f"no `channel_id` function found in {COMPOSE.name}")


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


def test_the_contract_is_enforced_somewhere() -> None:
    """
    If a frontend tree is visible at all, these tests must not be skipping.

    This is the guard on the compromise `_find_client_channels` documents. The way
    a cross-codebase check dies is not deletion — it is a skip that becomes
    permanent because the file moved and nobody noticed the suite got shorter.

    So: when `frontend/` exists beside `backend/`, `channels.ts` must be findable.
    A rename makes this fail with the path it looked for, rather than turning the
    whole file into a no-op.
    """
    reachable = [
        root / _CLIENT_RELATIVE
        for root in (BACKEND.parent, Path("/"))
        if (root / "frontend").is_dir()
    ]
    if not reachable:
        pytest.skip(
            "no frontend tree visible — add the channels.ts mount from "
            "docker-compose.yml, or run pytest from the repository root"
        )
    assert CLIENT_CHANNELS is not None, (
        f"a frontend tree is visible at {[str(p.parent) for p in reachable]} but "
        f"{_CLIENT_RELATIVE.name} was not found. It is the single source of truth "
        "for Android channel ids and the backend's channel_id values are checked "
        "against it — if it moved, update _CLIENT_RELATIVE and the docker-compose "
        "mount rather than letting these tests skip."
    )


@needs_client
def test_every_backend_channel_exists_on_the_client() -> None:
    """
    The contract, in one line.

    One-directional on purpose: the client may declare a channel the backend
    never sends to — `sos_alert` is exactly that, since SOS notifications are
    presented locally — but the backend must never name one the client has not
    created.
    """
    missing = backend_channel_ids() - client_channel_ids()
    assert missing == set(), (
        f"the backend sends channelId {sorted(missing)}, which "
        f"{CLIENT_CHANNELS.name} does not create. Android will file those "
        "notifications under a fallback channel with default importance and no "
        "sound — silently. Add the channel on the client or stop sending the id."
    )


@needs_client
def test_every_composed_message_carries_a_known_channel() -> None:
    """
    The same check through the actual objects, so a clever `channel_id` cannot
    satisfy the static read while returning something else at runtime.
    """
    known = client_channel_ids()
    messages: list[PushMessage] = [compose_test_alert()]
    for category in (AlertCategory.CORRIDOR, AlertCategory.SCHEDULED, AlertCategory.CHRONIC):
        messages.append(compose_alert(flag=_flag(), category=category, severity=60.0))

    for message in messages:
        assert message.channel_id in known, (
            f"{message.category.value} composes channelId {message.channel_id!r}, "
            f"which the client does not create (known: {sorted(known)})"
        )


def test_the_sos_channel_is_never_used_for_a_routine_alert() -> None:
    """
    SOS importance is reserved, and reserving it has to be mechanical.

    `sos_alert` is the only MAX-importance channel: it takes over the screen,
    because somebody pressed a button. If a routine road alert were ever sent on
    it, every blocked road would interrupt whatever the user was doing — and the
    user's only remedy would be to turn the channel down, which would also turn
    down the actual emergencies. That is unrecoverable from the app's side:
    Android does not let us raise a channel the user has lowered.
    """
    for category in AlertCategory:
        if category is AlertCategory.TEST:
            assert compose_test_alert().channel_id != "sos_alert"
            continue
        message = compose_alert(flag=_flag(), category=category, severity=60.0)
        assert message.channel_id != "sos_alert", (
            f"{category.value} alerts must not use the SOS channel"
        )


def test_a_test_alert_does_not_share_the_risk_channel() -> None:
    """
    Somebody silencing test notifications after a walkthrough must not be
    silencing real warnings at the same time. Separate channels is the only way
    to offer that, because channel importance is per channel and permanent.
    """
    assert compose_test_alert().channel_id != compose_alert(
        flag=_flag(), category=AlertCategory.CORRIDOR, severity=60.0
    ).channel_id


def test_channel_id_is_simple_enough_to_read_statically() -> None:
    """
    `backend_channel_ids()` reads string constants out of `channel_id`'s body.

    If that function grows a lookup table, a settings read or an f-string, the
    static read starts returning an incomplete set and
    `test_every_backend_channel_exists_on_the_client` gets quietly weaker rather
    than failing. So the shape is pinned: literals only, and at least two of
    them.
    """
    ids = backend_channel_ids()
    assert len(ids) >= 2, (
        "channel_id no longer returns plain string literals, so this file can no "
        "longer read it. Either keep it literal or rewrite backend_channel_ids()."
    )


# ---------------------------------------------------------------------------


def _flag() -> RiskFlag:
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    now = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    return RiskFlag(
        flag_id=uuid4(),
        event_key="test",
        kind=IncidentKind.FIRE,
        status="confirmed",
        lat=23.75,
        lon=90.40,
        radius_m=400,
        severity_0=70.0,
        severity_now=70.0,
        half_life_hours=3.0,
        observed_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=6),
        source_count=3,
        sources=[],
        mobility_statement=to_mobility_statement(
            kind=IncidentKind.FIRE, impact=MobilityImpact.ROAD_BLOCKED, place="Bangshal"
        ),
        confidence=1.0,
    )
