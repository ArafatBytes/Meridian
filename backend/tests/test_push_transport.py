"""
The Expo push transport: reading a receipt without blaming the wrong device.

B6a / S16. Not in `invariants/` — this is ordinary unit testing of a protocol
adapter, not a product commitment. It is here because one of these failures is
quietly destructive.

`HttpPushTransport._read_receipts` maps Expo's response array back onto the batch
that produced it. Expo returns one entry per message, in order, and the mapping is
positional — so a short or malformed `data` array zipped against the batch
attributes one device's failure to a different device. The consequence is not a
logged oddity: `DeviceNotRegistered` disables a token, so the wrong user silently
stops receiving safety alerts, and nothing anywhere says why.

That is why the length is checked rather than assumed, and why these tests exist.
"""

from __future__ import annotations

import asyncio

import pytest

from app.alerts.compose import PushMessage
from app.alerts.expo import (
    BATCH_SIZE,
    HttpPushTransport,
    NullPushTransport,
)
from app.alerts.policy import AlertCategory


def message(text: str = "Road blocked near Bangshal.") -> PushMessage:
    return PushMessage(
        title="On your route now", body=text, category=AlertCategory.CORRIDOR, data={}
    )


def batch(*tokens: str) -> list[tuple[str, PushMessage]]:
    return [(token, message()) for token in tokens]


read = HttpPushTransport._read_receipts  # a staticmethod; no client, no network


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_each_receipt_is_matched_to_its_own_token() -> None:
    receipts = read(
        batch("tok-a", "tok-b"),
        {"data": [{"status": "ok", "id": "r1"}, {"status": "ok", "id": "r2"}]},
    )
    assert [(r.token, r.ok, r.receipt_id) for r in receipts] == [
        ("tok-a", True, "r1"),
        ("tok-b", True, "r2"),
    ]


def test_a_dead_token_is_flagged_for_disabling() -> None:
    receipts = read(
        batch("tok-live", "tok-dead"),
        {
            "data": [
                {"status": "ok", "id": "r1"},
                {
                    "status": "error",
                    "message": "token is not a registered device",
                    "details": {"error": "DeviceNotRegistered"},
                },
            ]
        },
    )
    assert receipts[0].device_gone is False
    assert receipts[1].device_gone is True
    assert receipts[1].token == "tok-dead"


@pytest.mark.parametrize(
    "code", ["MessageTooBig", "MessageRateExceeded", "InvalidCredentials", "MismatchSenderId"]
)
def test_our_own_mistakes_do_not_disable_the_users_token(code: str) -> None:
    """
    Only `DeviceNotRegistered` justifies disabling a device.

    Every code here is *our* problem: a malformed message, our rate limit, our
    credentials. Treating them as "the device is gone" would quietly unsubscribe
    people from a product they are still using, and the next sweep would not even
    consider them. The failure mode is permanent and silent, which is the
    combination worth a test.
    """
    receipts = read(
        batch("tok-a"),
        {"data": [{"status": "error", "message": "nope", "details": {"error": code}}]},
    )
    assert receipts[0].ok is False
    assert receipts[0].device_gone is False, f"{code} must not disable a device"
    assert receipts[0].error


# ---------------------------------------------------------------------------
# The destructive failure: a response that does not line up
# ---------------------------------------------------------------------------


def test_a_short_response_fails_the_whole_batch_rather_than_mismatching() -> None:
    """
    Two messages, one receipt. Nothing may be attributed positionally.

    Zipping here would mark `tok-a` with the one receipt and leave `tok-b`
    unaccounted for — or, with `strict=False`, pair `tok-b`'s outcome with
    whatever came back for `tok-a`. If that entry were `DeviceNotRegistered`, a
    perfectly good token gets disabled.

    Failing all of them is the safe answer: the ledger rows are marked `rejected`,
    no token is touched, and the error names the response shape.
    """
    receipts = read(batch("tok-a", "tok-b"), {"data": [{"status": "ok", "id": "r1"}]})
    assert len(receipts) == 2
    assert [r.token for r in receipts] == ["tok-a", "tok-b"]
    assert all(not r.ok for r in receipts)
    assert all(not r.device_gone for r in receipts)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": None},
        {"data": "not a list"},
        {"errors": [{"code": "PUSH_TOO_MANY_EXPERIENCE_IDS"}]},
        "not even an object",
        None,
    ],
)
def test_an_unusable_response_is_reported_per_message(body: object) -> None:
    """
    Every shape Expo might return on a bad day yields one receipt per input.

    `PushTransport` promises a receipt for every input so no caller has to reason
    about a short list. These are the shapes that would otherwise return
    something shorter, or raise inside the dispatcher's loop and abandon the rest
    of the sweep.
    """
    receipts = read(batch("tok-a", "tok-b", "tok-c"), body)
    assert len(receipts) == 3
    assert all(not r.ok and r.error for r in receipts)


def test_an_entry_that_is_not_an_object_fails_only_its_own_message() -> None:
    """A malformed single entry must not condemn its neighbours."""
    receipts = read(
        batch("tok-a", "tok-b"),
        {"data": ["garbage", {"status": "ok", "id": "r2"}]},
    )
    assert receipts[0].ok is False
    assert receipts[1].ok is True
    assert receipts[1].token == "tok-b"


def test_an_error_with_no_details_still_produces_a_message() -> None:
    """
    Expo does not always send `details`. An empty `error` would make a rejected
    ledger row indistinguishable from a successful one in the history.
    """
    receipts = read(batch("tok-a"), {"data": [{"status": "error"}]})
    assert receipts[0].ok is False
    assert receipts[0].error == "unknown Expo error"


# ---------------------------------------------------------------------------
# Batching and the dry run
# ---------------------------------------------------------------------------


def test_the_batch_size_is_expos_limit_not_a_preference() -> None:
    """100 is what the push API accepts per request. Not a tuning knob."""
    assert BATCH_SIZE == 100


def test_the_null_transport_sends_nothing_and_records_everything() -> None:
    """
    `dry_run` must reach the transport, not just the writes.

    Sending a notification is the least reversible thing this system does. A dry
    run that still buzzed a phone would be useless for the rehearsal it exists
    for — so the null transport reports success, delivers nothing, and keeps what
    it was asked to send so a test can assert on it.
    """
    transport = NullPushTransport()
    receipts = asyncio.run(transport.send(batch("tok-a", "tok-b")))
    assert [r.ok for r in receipts] == [True, True]
    assert [token for token, _ in transport.sent] == ["tok-a", "tok-b"]


def test_default_transport_is_null_when_push_is_disabled() -> None:
    """
    `PUSH_ENABLED` defaults off, because remote push cannot work until somebody
    has uploaded FCM credentials to EAS — account setup, not code.

    With it off the dispatcher still runs, still applies policy and still writes
    the ledger. What it must not do is report success while Expo rejects every
    message for want of credentials.
    """
    from app.alerts.expo import default_transport
    from app.core.config import settings

    assert isinstance(default_transport(dry_run=True), NullPushTransport)
    if not settings.PUSH_ENABLED:
        assert isinstance(default_transport(dry_run=False), NullPushTransport)
