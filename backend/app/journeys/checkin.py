"""
What the check-in says, and the two ids the app has to agree with. JG2.

One notification, one question, one button. This module is the whole vocabulary
of it, and it is a constant rather than a template for the same reason
`alerts/compose.py` is: a notification is the most public thing this system
emits, it arrives unasked on a lock screen, and it may be the only sentence about
the situation that anybody reads.

## It says nothing about where you are

Not "still near Sobhanbagh?", not the destination, not the time you set. A
check-in appears on a lock screen, which is visible to whoever is standing next
to the person -- and JOURNEY_GUARDIAN.md §5 is explicit that the dangerous case
is the one where that person is watching her answer it. A notification naming her
destination tells him where she is going; one naming her deadline tells him how
long he has. Neither is information this product should hand to him for free.

So the text is deliberately bland and could be about anything. The journey id
rides in `data`, where the app reads it and the lock screen does not show it.

## The two cross-codebase ids

`CHECK_IN_CHANNEL` and `CHECK_IN_ACTION_CATEGORY` are strings that this codebase
and the app must spell identically, with nothing at build time to check them. If
the channel disagrees, Android files the notification under a fallback with
default importance and no sound -- silently. If the action category disagrees, the
notification arrives with **no buttons**, which turns the one-tap answer into
"open the app and find the journey card", and nothing reports that either.

`tests/invariants/test_journey_deadline.py` reads the app's source for both.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from app.alerts.compose import PushMessage

__all__ = [
    "CHECK_IN_ACTION_CATEGORY",
    "CHECK_IN_ACTION_OK",
    "CHECK_IN_CHANNEL",
    "compose_check_in",
]


CHECK_IN_CHANNEL: Final = "journey_check_in"
"""
The Android channel, and it has to be its own.

Not `risk_alert`: somebody who silences road alerts -- a reasonable thing to do
after a noisy week -- must not discover they have also silenced the question that
asks whether they got home. Android channel importance is user-controlled and
permanent; an app cannot raise a channel the user has lowered, so the split has
to exist before anybody lowers anything.

Not `sos_alert` either, whose own note in `channels.ts` says it never shares:
it is MAX importance and takes over the screen because somebody pressed a button.
A check-in is a question, not an emergency, and borrowing the emergency channel
would train people to ignore it.
"""

CHECK_IN_ACTION_CATEGORY: Final = "journey_check_in"
"""
The Expo notification category id — the thing that puts a button on the lock
screen. Same string as the channel by coincidence of naming, not by requirement;
they are different namespaces and the app registers them separately.
"""

CHECK_IN_ACTION_OK: Final = "journey_ok"
"""
The id of the one button.

One, not two. JOURNEY_GUARDIAN.md §5 describes a second button that looks
identical and silently escalates instead -- that is JG6, and it needs the
escalation chain JG3 builds before it can do anything but lie. A decoy button
wired to the same endpoint as the real one would be worse than no decoy: it would
teach someone to trust a control that does nothing.
"""


_TITLE: Final = "Are you there yet?"
_BODY: Final = "Tap to let Meridian know you're fine."
_BUTTON: Final = "I'm fine"
"""
The button's own label, kept here so the app and the backend can be checked
against each other -- Android draws the label the *app* registered, not one sent
with the message, so a disagreement is invisible until somebody reads both files.
"""


def compose_check_in(*, journey_id: UUID | str) -> PushMessage:
    """
    The check-in notification for one journey.

    No `AlertCategory`: this is not a risk alert, does not go through
    `sent_alerts`, and is deliberately exempt from the hourly rate cap. See
    `PushMessage.category`.
    """
    return PushMessage(
        title=_TITLE,
        body=_BODY,
        channel=CHECK_IN_CHANNEL,
        action_category=CHECK_IN_ACTION_CATEGORY,
        # `type` is what the app's existing tap handler switches on; `journeyId`
        # is what the action handler posts the answer against. Both are read from
        # `data` and neither is rendered, so neither appears on the lock screen.
        data={"type": "journey_check_in", "journeyId": str(journey_id)},
    )
