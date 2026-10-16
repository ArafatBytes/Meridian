"""
Journey Guardian wire shapes. JG1, extended by JG2 and JG3.

What the app sends when someone presses Start, what it reads back when the app
launches, the one number a heartbeat carries, and -- since JG3 -- the one
person who is told about any of it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class JourneyStart(BaseModel):
    """
    The journey being started, as the route card knows it.

    Everything here comes from state the map screen already has: the two
    endpoints it routed between, the label in the destination field, and the
    selected `RouteResponse`. Nothing is computed on the client that the server
    needs to trust -- `eta_at` in particular is derived server-side from
    `started_at + duration_minutes`, because a clock the client sets is a
    deadline the client can move, and from JG2 onward that deadline is the
    feature.

    `deadline_minutes` is the one exception, and it is a narrow one: the person
    is allowed to choose how long they are giving themselves, because the router
    does not know they are stopping for food. What they cannot do is choose where
    that lands -- the server reads the minutes, clamps them and computes the
    instant from its own clock. See `app/journeys/deadline.py`.
    """

    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)

    #: What the person called the place. Trimmed and capped rather than
    #: validated: it is whatever was in the search box, including a POI name
    #: from a map tap, and it is only ever displayed back to its own author.
    destination_label: str = Field(..., min_length=1, max_length=200)

    route_id: str | None = Field(None, max_length=200)
    route_profile: Literal["driving", "foot"]

    distance_km: float = Field(..., ge=0, le=10_000)
    duration_minutes: float = Field(..., ge=0, le=24 * 60)
    safety_score: float | None = Field(None, ge=0, le=100)

    #: Minutes from now, as chosen at start. `None` means the person accepted
    #: the default, which is the route's own ETA plus the grace period.
    #:
    #: The bounds here are the wire's sanity check and not the policy: the real
    #: clamp is `MIN_DEADLINE`/`MAX_DEADLINE` in `journeys/deadline.py`, and it
    #: is applied to the default as well as to a choice. Two bounds rather than
    #: one because a schema that accepted 50,000 would make the clamp the only
    #: thing standing between a typo and a journey due next Tuesday.
    deadline_minutes: int | None = Field(None, ge=1, le=24 * 60)

    #: JG3. The one person told about this journey, as an `emergency_contacts`
    #: id. `None` means nobody is told.
    #:
    #: **None is the default and that is deliberate.** Silently emailing
    #: whoever happens to be first in somebody's contact list, because they
    #: pressed Start, is the kind of surprise that loses trust permanently --
    #: and it is not recoverable, because the message has already arrived. A
    #: journey nobody is told about is JG2's behaviour, which works, so the
    #: safe default is also the one that needs no explanation.
    #:
    #: The id is checked against the caller's own contacts before it is
    #: written. An unvalidated id here would let a request name a row belonging
    #: to another account and have Meridian email a stranger about a journey
    #: they have nothing to do with -- see `_CONTACT_IS_MINE` in the endpoint.
    guardian_contact_id: UUID | None = None


class JourneyHeartbeat(BaseModel):
    """
    The phone saying it is still going, and roughly how much is left.

    One number, and deliberately no position. JG2 has no reader for a location:
    the check-in goes to the person's own phone, and the only message that needs
    a last known position is the escalation JG3 sends to somebody else. See the
    migration header.

    `remaining_seconds` is the navigator's own live estimate -- `remainingSeconds`
    in `useNavigation` -- which is computed from measured GPS progress rather than
    from the route's original promise. That is what makes a jam extend the
    deadline honestly: the phone says "still going, longer than I thought", and
    the clock follows.
    """

    remaining_seconds: float = Field(..., ge=0, le=24 * 60 * 60)

    #: JG3. Where the phone is, and **optional on purpose**.
    #:
    #: JG2 had no field here at all, enforced by a test whose own reasoning said
    #: the only reader would be the escalation JG3 sends to somebody else. JG3
    #: is that reader, so the field arrives with its first consumer rather than
    #: ahead of it.
    #:
    #: Optional, in both directions:
    #:
    #: * The **app** declines to send one when the journey has no guardian,
    #:   because nobody could ever be shown it.
    #: * The **server** declines to store one for the same reason, in the same
    #:   statement that writes the heartbeat. Two enforcements of one rule, so
    #:   neither a stale build nor a future client can be the thing that makes
    #:   a position appear on a journey nobody is watching.
    #:
    #: A heartbeat with no fix still slides the deadline. Being unable to see
    #: the sky is not evidence that somebody is late.
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class JourneyResponse(BaseModel):
    """
    A journey as the app reads it. The whole visible output of JG1 is one
    sentence built from `duration_minutes` and `destination_label` -- "12 min to
    Mirpur" -- plus the two coordinates needed to put the route back on screen.
    """

    journey_id: str
    state: Literal["active", "arrived", "cancelled"]

    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    destination_label: str

    route_id: str | None = None
    route_profile: str
    distance_km: float
    duration_minutes: float
    safety_score: float | None = None

    started_at: datetime
    eta_at: datetime
    ended_at: datetime | None = None

    # ---- JG2: the clock, and the one question ----------------------------

    #: When the server expects you. Moved only by a heartbeat or an answer.
    deadline_at: datetime

    #: How worried the server is, in five states.
    #:
    #: This listed two of them until JG3, and leaving it that way would have
    #: been the most embarrassing failure available: a journey that escalated
    #: became **unreadable**. Pydantic validates responses as well as requests,
    #: so `GET /journeys/active` on a journey in `check_in_repeated` raised a
    #: ValidationError and returned a 500 -- the app would lose the journey at
    #: the exact moment the feature started working. Confirmed by constructing
    #: one of these per state; three of the four were rejected.
    #:
    #: Written out rather than built from `ESCALATION_STATES` because a
    #: `Literal` needs its members at type-check time. The invariant test
    #: compares the two lists instead.
    escalation_state: Literal[
        "normal",
        "check_in_sent",
        "check_in_repeated",
        "contacts_notified",
        "full_sos",
    ]

    #: When the current question was asked, when it was answered, and when the
    #: sweep observed it go unanswered. All three are history rather than state:
    #: `answered_at` survives the return to `normal`, which is why the app
    #: compares it against `check_in_sent_at` rather than reading it alone.
    check_in_sent_at: datetime | None = None
    answered_at: datetime | None = None
    unanswered_at: datetime | None = None

    last_heartbeat_at: datetime | None = None

    # ---- JG3: the rest of the ladder, and who is being told ---------------

    #: The other three rungs, stamped as each one fires. With the three above
    #: they are the whole history of this journey's outstanding question --
    #: there is no events table, which is a deliberate scope choice, so the
    #: journey screen's timeline is built from exactly these.
    #:
    #: All of them are cleared when a **new** question is asked, so they
    #: describe the current cycle and not the trip. A journey asked, answered
    #: and asked again has nothing left from the first round, and that is the
    #: only shape the ordering CHECKs permit.
    check_in_repeated_at: datetime | None = None
    contacts_notified_at: datetime | None = None
    full_sos_at: datetime | None = None

    #: Who is being told, and their name for the one line on the card.
    #:
    #: The name comes from the server rather than being looked up in the app's
    #: own contact list, because the app would have to load every contact to
    #: render one word -- and after a cold start, on the journey the phone was
    #: force-stopped out of, it may not have them yet. Null means nobody,
    #: which is the default.
    guardian_contact_id: str | None = None
    guardian_name: str | None = None

    #: When the guardian was actually emailed -- not when the journey started.
    #: The gap between `started_at` and this is the sweep's cadence, and the
    #: difference matters on the journey screen: "Ammu was told" is only true
    #: once this is set, and an SMTP failure leaves it null on purpose so the
    #: next sweep retries.
    started_notice_at: datetime | None = None
    arrived_notice_at: datetime | None = None
