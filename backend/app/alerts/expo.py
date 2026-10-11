"""
Getting a notification onto a phone. B6a / S16.

The transport, and nothing else: it knows about Expo's HTTP API and about push
tokens, and it has no opinion about whether a notification should be sent. That
decision is `policy.py`'s and its wording is `compose.py`'s.

## Why Expo's relay rather than FCM directly

`expo-notifications` is already in the app and already configured in `app.json`,
and S16 names *"EAS project id"* explicitly, so the Expo push service is the
intended path. The alternative — holding Firebase service-account credentials on
the backend and talking to FCM v1 directly — buys per-platform control this
product does not need yet and costs a second credential to rotate. Should it ever
be wanted, `PushTransport` is the seam: implement it and nothing above this file
changes.

The cost of the relay is honest and worth stating: a notification passes through
Expo's servers. Nothing sensitive goes in one — `compose.py` emits a mobility
statement already published on the public map, plus a flag id — but "passes
through a third party" belongs in the privacy register (B14) rather than only in
a code comment.

## What this file deliberately does not do

**It does not fetch delivery receipts.** Expo's `/push/getReceipts` answers, some
seconds later, whether FCM or APNs actually accepted each notification. Reading
them would need a second scheduled pass and a `pending` state in the ledger, and
it answers a question nobody is asking yet.

What it *would* catch, and what is therefore currently invisible, is a credential
problem that only the device layer sees — an FCM key revoked after the token was
issued. `DeviceNotRegistered` is caught synchronously and handled below, which is
the failure that actually accumulates; the rest shows up as "the push never
arrived" and has to be diagnosed by hand. That is a real gap, written down rather
than implied, and `docs/walkthroughs/B6a.md` says how to check it manually.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Protocol

import httpx

from app.alerts.compose import PushMessage
from app.core.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "BATCH_SIZE",
    "HttpPushTransport",
    "NullPushTransport",
    "PushReceipt",
    "PushTransport",
    "default_transport",
]

EXPO_PUSH_URL: Final[str] = "https://exp.host/--/api/v2/push/send"

BATCH_SIZE: Final[int] = 100
"""
Expo accepts at most 100 messages per request. Not a tuning knob — their limit.
"""

TIMEOUT_S: Final[float] = 15.0

_DEVICE_GONE: Final[frozenset[str]] = frozenset({"DeviceNotRegistered"})
"""
Expo error codes that mean the token is dead and must not be retried.

Narrow on purpose. `MessageTooBig`, `MessageRateExceeded` and `InvalidCredentials`
are all *our* problems, not the device's, and disabling a user's token because we
sent a malformed message would quietly unsubscribe them from a product they are
still using. Only `DeviceNotRegistered` — the app was uninstalled, or the token
was rotated — justifies that.
"""


@dataclass(frozen=True, slots=True)
class PushReceipt:
    """
    What Expo said about one message, in our terms.

    `token` rather than an index, because the caller has to map an outcome back
    to a `push_devices` row and matching by list position across a batched,
    partially-failed send is how a disable gets applied to the wrong device.
    """

    token: str
    ok: bool
    receipt_id: str | None = None
    error: str | None = None
    device_gone: bool = False


class PushTransport(Protocol):
    """
    Anything that can deliver notifications.

    A protocol so the dispatcher can be tested end to end without a network: the
    tests pass a recording implementation and assert on what it was asked to
    send. That is also what makes `dry_run` honest — see `NullPushTransport`.
    """

    async def send(self, messages: list[tuple[str, PushMessage]]) -> list[PushReceipt]:
        """
        Deliver `(expo_push_token, message)` pairs. One receipt per input, in order.

        Implementations must return a receipt for every input even when the whole
        request failed, so the caller never has to reason about a short list.
        """
        ...


class NullPushTransport:
    """
    Delivers nothing and reports success. The `dry_run` transport.

    `AgentContext.dry_run` *must* reach every write path — "an agent that ignores
    it is a bug, not a style choice" (`contracts/agents.py`). Sending a real
    notification is the least reversible write this system performs: a dry run
    that still buzzed somebody's phone would make the flag useless for exactly
    the rehearsal it exists for.
    """

    def __init__(self, reason: str = "dry-run") -> None:
        # The reason is in the log line because the two causes need telling
        # apart. `PUSH_ENABLED=false` means the account setup in
        # docs/walkthroughs/B6a.md is not done; `--dry-run` means somebody asked
        # for a rehearsal. A single "[dry-run]" label for both — which is what
        # this printed first — sends you looking for a flag you did not pass.
        self.reason = reason
        self.sent: list[tuple[str, PushMessage]] = []

    async def send(self, messages: list[tuple[str, PushMessage]]) -> list[PushReceipt]:
        self.sent.extend(messages)
        for token, message in messages:
            logger.info(
                "[%s] would push to %s: %s / %s",
                self.reason,
                token,
                message.title,
                message.body,
            )
        return [PushReceipt(token=token, ok=True) for token, _ in messages]


class HttpPushTransport:
    """
    The real one: Expo's push API over HTTPS.

    One `AsyncClient` per instance, closed by `aclose()`. The dispatcher builds
    one per run and closes it in a `finally` — a client leaked once a minute by
    Celery beat is a slow file-descriptor exhaustion, and it took a while to find
    the last time something in this project did that.
    """

    def __init__(self, *, access_token: str | None = None) -> None:
        headers = {
            "Content-Type": "application/json",
            # Expo's docs ask for these two; they let the service reject
            # oversized payloads before reading the body.
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        token = access_token if access_token is not None else settings.EXPO_ACCESS_TOKEN
        if token:
            # Only needed when the Expo project has "enhanced security for push
            # notifications" switched on. Harmless otherwise, so it is sent
            # whenever configured rather than behind another flag.
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(headers=headers, timeout=TIMEOUT_S)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send(self, messages: list[tuple[str, PushMessage]]) -> list[PushReceipt]:
        receipts: list[PushReceipt] = []
        for start in range(0, len(messages), BATCH_SIZE):
            batch = messages[start : start + BATCH_SIZE]
            receipts.extend(await self._send_batch(batch))
        return receipts

    async def _send_batch(self, batch: list[tuple[str, PushMessage]]) -> list[PushReceipt]:
        payload = [
            {
                "to": token,
                "title": message.title,
                "body": message.body,
                "data": message.data,
                "sound": "default",
                "channelId": message.channel_id,
                # `high` rather than `max`. `max` asks Android to interrupt
                # whatever the user is doing with a full-screen heads-up, and it
                # is reserved for the SOS path, where somebody has pressed a
                # button. A road being blocked is important and is not that.
                "priority": "high",
                # If it could not be delivered within an hour, do not deliver it.
                # A notification about a road that was blocked last night is
                # noise at best and misleading at worst — the flag has decayed
                # and may have expired, and the user cannot tell that from a
                # lock screen.
                "ttl": 3600,
            }
            for token, message in batch
        ]

        try:
            response = await self._client.post(EXPO_PUSH_URL, json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as problem:
            # The whole request failed, so nothing is known about any individual
            # message. Report every one as failed: the ledger rows were written
            # before the send (see the migration), and marking them `rejected`
            # is the truthful outcome. They still count against the rate cap,
            # which is the deliberate trade — see the migration's reasoning.
            logger.warning("Expo push request failed for %d messages: %s", len(batch), problem)
            return [
                PushReceipt(token=token, ok=False, error=str(problem)) for token, _ in batch
            ]

        return self._read_receipts(batch, body)

    @staticmethod
    def _read_receipts(
        batch: list[tuple[str, PushMessage]], body: object
    ) -> list[PushReceipt]:
        """
        Turn Expo's response into one receipt per input.

        Expo answers `{"data": [ ... ]}` with one entry per message in order, and
        may also answer `{"errors": [...]}` for a request-level problem. The
        length is checked rather than assumed: a short `data` array zipped
        positionally against the batch would attribute one device's failure to a
        different device, and the consequence of that is disabling the wrong
        user's push token.
        """
        entries = body.get("data") if isinstance(body, dict) else None
        if not isinstance(entries, list) or len(entries) != len(batch):
            detail = (
                body.get("errors") if isinstance(body, dict) else None
            ) or "unexpected response shape"
            logger.warning("Expo push response not usable: %s", detail)
            return [
                PushReceipt(token=token, ok=False, error=str(detail)) for token, _ in batch
            ]

        receipts: list[PushReceipt] = []
        for (token, _), entry in zip(batch, entries, strict=True):
            if not isinstance(entry, dict):
                receipts.append(
                    PushReceipt(token=token, ok=False, error="unexpected receipt shape")
                )
                continue
            if entry.get("status") == "ok":
                receipts.append(PushReceipt(token=token, ok=True, receipt_id=entry.get("id")))
                continue
            details = entry.get("details")
            code = details.get("error") if isinstance(details, dict) else None
            receipts.append(
                PushReceipt(
                    token=token,
                    ok=False,
                    error=entry.get("message") or code or "unknown Expo error",
                    device_gone=code in _DEVICE_GONE,
                )
            )
        return receipts


def default_transport(*, dry_run: bool) -> PushTransport:
    """
    The transport a run should use.

    Returns the null transport for a dry run, and also when `PUSH_ENABLED` is
    off. The flag defaults to off because remote push cannot work until somebody
    has created an Expo project and uploaded FCM credentials — account setup, not
    code — and an endpoint that reports success while Expo rejects every message
    for want of credentials is the kind of thing that gets discovered on stage.
    With it off, the dispatcher still runs, still applies policy and still writes
    the ledger, so everything except delivery is observable.
    """
    if dry_run:
        return NullPushTransport("dry-run")
    if not settings.PUSH_ENABLED:
        return NullPushTransport("PUSH_ENABLED=false")
    return HttpPushTransport()
