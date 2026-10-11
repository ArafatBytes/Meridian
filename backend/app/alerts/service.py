"""
The alert pipeline, against the database. B6a / S16.

Three jobs, and they are kept apart because they fail for different reasons:

    devices      register, refresh, disable          `push_devices`
    preferences  read with defaults, write           `notification_preferences`
    dispatch     decide, send, record                `sent_alerts` + a transport

Everything here is I/O over shapes defined elsewhere. The *decision* lives in
`policy.py` and the *wording* in `compose.py`, both pure; this module reads rows,
hands them to those two, and writes down what happened. Keeping it that way is
what lets the fatigue rules be tested without Postgres.

## Devices drive the sweep, not flags

`dispatch_for_devices` iterates devices and asks the risk surface what is near
each one. The obvious alternative — iterate newly published flags and find the
devices near them — was rejected for one reason: it needs a query against
`risk_flags`, and *"everything that consumes risk talks to a `RiskSurface` and
never to a table"* (`contracts/surface.py`).

Going through the surface means alert dispatch works unchanged when
`RISK_SURFACE_IMPL=seeded`, which is the offline demo path D10's failure drills
switch to. A dispatcher that queried the table directly would be the one
component that stopped working the moment the venue network died — and it is the
component whose job is to tell people a road is blocked.

The cost is that work scales with devices rather than with new flags. At this
project's scale that is nothing; at a scale where it mattered, the fix is to
bound it by only considering devices whose location was refreshed recently, which
`DEVICE_LOCATION_MAX_AGE` already does for a different reason.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.compose import PushMessage, compose_alert, compose_test_alert
from app.alerts.expo import PushReceipt, PushTransport
from app.alerts.policy import (
    RATE_WINDOW,
    AlertCategory,
    AlertPreferences,
    plan_for_device,
)
from app.contracts.risk import RiskFlag
from app.contracts.surface import RiskSurface
from app.core.config import settings

logger = logging.getLogger(__name__)

POSTGIS_SCHEMA: Final[str] = "extensions"
"""Supabase installs PostGIS here, not in `public`. See `scoring/surface_db.py`."""

__all__ = [
    "DEVICE_LOCATION_MAX_AGE",
    "DispatchOutcome",
    "DeviceRow",
    "delete_device",
    "dispatch_for_devices",
    "load_preferences",
    "read_history",
    "register_device",
    "save_preferences",
    "send_test_alert",
]

DEVICE_LOCATION_MAX_AGE: Final = timedelta(hours=6)
"""
How old a device's last known position may be and still be alerted on.

Six hours, and the number is a judgement about being wrong in public. The
position comes from the app's last foreground moment (background location is S17
and is not built), so it is routinely hours stale. Alerting someone about a road
near where they were yesterday is not a warning, it is noise that teaches them to
ignore the next one.

Six is long enough to cover a working day's commute — open the app in the
morning, be alerted about the route home — and short enough that an overnight
position is dropped. It is deliberately NOT the same as the flag's own lifetime:
a flag can be fresh while our idea of where the user is has gone stale, and that
is the case this guards.
"""


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DeviceRow:
    """One row of `push_devices`, as the dispatcher needs it."""

    id: UUID
    user_id: UUID
    expo_push_token: str
    lat: float
    lon: float
    last_location_at: datetime


async def register_device(
    db: AsyncSession,
    *,
    user_id: UUID,
    expo_push_token: str,
    platform: str,
    app_version: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    now: datetime,
) -> UUID:
    """
    Register or refresh one install's delivery address, and where it is.

    Upserts on `expo_push_token`, overwriting `user_id`. That is the behaviour a
    shared or resold phone needs: the token identifies the install, so when a
    different person signs in on it their alerts must replace the previous
    owner's rather than being delivered alongside them.

    `disabled_at` is cleared on every registration. A reinstall issues the same
    token and must come back to life; leaving it disabled would mean a user who
    reinstalled to fix notifications had permanently broken them.

    Location is optional and partial updates are supported deliberately: the app
    calls this on every foreground with a token always and a position only when
    it has one. `coalesce` keeps the last known position rather than wiping it
    when permission is momentarily unavailable — a stale position is handled by
    `DEVICE_LOCATION_MAX_AGE`, which is a better-understood failure than no
    position at all.
    """
    has_location = lat is not None and lon is not None
    statement = text(
        f"""
        INSERT INTO public.push_devices (
            user_id, expo_push_token, platform, app_version,
            last_location, last_location_at
        )
        VALUES (
            :user_id, :token, :platform, :app_version,
            CASE WHEN :has_location THEN
                {POSTGIS_SCHEMA}.ST_SetSRID(
                    {POSTGIS_SCHEMA}.ST_MakePoint(:lon, :lat), 4326
                )::{POSTGIS_SCHEMA}.geography
            END,
            CASE WHEN :has_location THEN cast(:now as timestamptz) END
        )
        ON CONFLICT (expo_push_token) DO UPDATE SET
            user_id          = excluded.user_id,
            platform         = excluded.platform,
            app_version      = coalesce(excluded.app_version, public.push_devices.app_version),
            last_location    = coalesce(excluded.last_location,
                                        public.push_devices.last_location),
            last_location_at = coalesce(excluded.last_location_at,
                                        public.push_devices.last_location_at),
            disabled_at      = NULL,
            disabled_reason  = NULL
        RETURNING id
        """
    )
    row = (
        await db.execute(
            statement,
            {
                "user_id": str(user_id),
                "token": expo_push_token,
                "platform": platform,
                "app_version": app_version,
                "has_location": has_location,
                "lat": lat,
                "lon": lon,
                "now": now,
            },
        )
    ).one()
    await db.commit()
    # `RETURNING id` is a uuid column, but Result rows are untyped, so the cast
    # is explicit rather than silently Any -- app.alerts.* is on mypy's strict list.
    return UUID(str(row[0]))


async def delete_device(db: AsyncSession, *, user_id: UUID, expo_push_token: str) -> bool:
    """
    Forget one install. Called on sign-out.

    Scoped to `user_id` as well as the token so that knowing a token is not
    enough to unsubscribe somebody else. Hard delete rather than disable: this is
    a user asking to stop being contacted, and the row holds a delivery address,
    so keeping it would be keeping contact details after being asked not to.
    `sent_alerts.device_id` is `ON DELETE SET NULL`, so the history survives.
    """
    result = await db.execute(
        text(
            """
            DELETE FROM public.push_devices
            WHERE user_id = :user_id AND expo_push_token = :token
            RETURNING id
            """
        ),
        {"user_id": str(user_id), "token": expo_push_token},
    )
    await db.commit()
    # `RETURNING id` rather than `result.rowcount`: `rowcount` is not on the
    # async `Result` protocol at all, so reading it was both untyped and, on some
    # drivers, -1 for a DELETE. A returned row is unambiguous.
    return result.first() is not None


async def count_devices(db: AsyncSession, *, user_id: UUID) -> dict[str, int]:
    """
    How many installs this user has registered, live and disabled.

    Read by `GET /notifications/config`, which exists to answer "why did nothing
    arrive". `{"active": 0}` is the most common answer and the most useful one:
    it means the app never obtained a token, which is a different problem from a
    rejected send and is fixed in a different place.
    """
    row = (
        await db.execute(
            text(
                """
                SELECT count(*) FILTER (WHERE disabled_at IS NULL)     AS active,
                       count(*) FILTER (WHERE disabled_at IS NOT NULL) AS disabled,
                       count(*) FILTER (
                           WHERE disabled_at IS NULL AND last_location IS NOT NULL
                       ) AS located
                FROM public.push_devices
                WHERE user_id = :user_id
                """
            ),
            {"user_id": str(user_id)},
        )
    ).one()
    return {"active": int(row.active), "disabled": int(row.disabled), "located": int(row.located)}


async def _disable_device(db: AsyncSession, *, token: str, reason: str, now: datetime) -> None:
    """Mark a token dead after Expo reported `DeviceNotRegistered`."""
    await db.execute(
        text(
            """
            UPDATE public.push_devices
            SET disabled_at = cast(:now as timestamptz), disabled_reason = :reason
            WHERE expo_push_token = :token
            """
        ),
        {"token": token, "reason": reason[:500], "now": now},
    )


async def _active_devices(db: AsyncSession, *, now: datetime) -> list[DeviceRow]:
    """
    Every device worth dispatching to: enabled, located, and located recently.

    `ST_Y` is latitude and `ST_X` is longitude — PostGIS stores points as
    (x, y) = (lon, lat), which is the opposite order from every other part of
    this system. Getting it backwards puts Dhaka in the Indian Ocean, and it is
    silent: the query succeeds and simply matches nothing.
    """
    result = await db.execute(
        text(
            f"""
            SELECT id,
                   user_id,
                   expo_push_token,
                   {POSTGIS_SCHEMA}.ST_Y(last_location::{POSTGIS_SCHEMA}.geometry) AS lat,
                   {POSTGIS_SCHEMA}.ST_X(last_location::{POSTGIS_SCHEMA}.geometry) AS lon,
                   last_location_at
            FROM public.push_devices
            WHERE disabled_at IS NULL
              AND last_location IS NOT NULL
              AND last_location_at >= cast(:cutoff as timestamptz)
            ORDER BY user_id, last_location_at DESC
            """
        ),
        {"cutoff": now - DEVICE_LOCATION_MAX_AGE},
    )
    return [
        DeviceRow(
            id=row.id,
            user_id=row.user_id,
            expo_push_token=row.expo_push_token,
            lat=float(row.lat),
            lon=float(row.lon),
            last_location_at=row.last_location_at,
        )
        for row in result
    ]


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

async def load_preferences(db: AsyncSession, user_ids: list[UUID]) -> dict[UUID, AlertPreferences]:
    """
    Preferences for these users, defaults where there is no row.

    Bulk rather than per-user because the dispatcher needs all of them at once; a
    sweep doing one query per device is the shape that makes a minute-cadence
    agent expensive. Users with no row are simply absent from the result and
    callers use `DEFAULT_PREFERENCES` — which is why `decide` takes preferences as
    an argument rather than looking them up.
    """
    if not user_ids:
        return {}
    result = await db.execute(
        text(
            """
            SELECT user_id, corridor_alerts, scheduled_alerts, chronic_alerts,
                   min_severity, quiet_hours_start, quiet_hours_end, max_per_hour
            FROM public.notification_preferences
            WHERE user_id = ANY(:user_ids)
            """
        ),
        {"user_ids": [str(uid) for uid in user_ids]},
    )
    return {
        row.user_id: AlertPreferences(
            corridor_alerts=row.corridor_alerts,
            scheduled_alerts=row.scheduled_alerts,
            chronic_alerts=row.chronic_alerts,
            min_severity=float(row.min_severity),
            quiet_hours_start=row.quiet_hours_start,
            quiet_hours_end=row.quiet_hours_end,
            max_per_hour=row.max_per_hour,
        )
        for row in result
    }


async def save_preferences(
    db: AsyncSession, *, user_id: UUID, prefs: AlertPreferences
) -> AlertPreferences:
    """
    Write one user's preferences, creating the row if needed.

    Full replacement, not a patch: the screen sends the whole object, and a
    partial update over seven fields is a source of "I turned that off and it
    came back" bug reports that nobody can reproduce.
    """
    await db.execute(
        text(
            """
            INSERT INTO public.notification_preferences (
                user_id, corridor_alerts, scheduled_alerts, chronic_alerts,
                min_severity, quiet_hours_start, quiet_hours_end, max_per_hour
            )
            VALUES (
                :user_id, :corridor, :scheduled, :chronic,
                :min_severity, :qh_start, :qh_end, :max_per_hour
            )
            ON CONFLICT (user_id) DO UPDATE SET
                corridor_alerts   = excluded.corridor_alerts,
                scheduled_alerts  = excluded.scheduled_alerts,
                chronic_alerts    = excluded.chronic_alerts,
                min_severity      = excluded.min_severity,
                quiet_hours_start = excluded.quiet_hours_start,
                quiet_hours_end   = excluded.quiet_hours_end,
                max_per_hour      = excluded.max_per_hour
            """
        ),
        {
            "user_id": str(user_id),
            "corridor": prefs.corridor_alerts,
            "scheduled": prefs.scheduled_alerts,
            "chronic": prefs.chronic_alerts,
            "min_severity": prefs.min_severity,
            "qh_start": prefs.quiet_hours_start,
            "qh_end": prefs.quiet_hours_end,
            "max_per_hour": prefs.max_per_hour,
        },
    )
    await db.commit()
    return prefs


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

async def _alerted_flag_ids(db: AsyncSession, user_ids: list[UUID]) -> dict[UUID, set[UUID]]:
    """
    Which flags each user has already been alerted about — ever.

    Not windowed. The debounce is "one alert per flag, ever", so the whole
    history is the answer. That grows without bound in principle; in practice a
    flag's lifetime is hours and a user accumulates a handful a day, and B14's
    retention registry is where trimming it belongs rather than here, where a
    cutoff would silently re-enable duplicate alerts for old flags.
    """
    if not user_ids:
        return {}
    result = await db.execute(
        text(
            """
            SELECT user_id, flag_id
            FROM public.sent_alerts
            WHERE user_id = ANY(:user_ids)
            """
        ),
        {"user_ids": [str(uid) for uid in user_ids]},
    )
    seen: dict[UUID, set[UUID]] = {}
    for row in result:
        seen.setdefault(row.user_id, set()).add(row.flag_id)
    return seen


async def _sent_in_window(
    db: AsyncSession, user_ids: list[UUID], *, now: datetime
) -> dict[UUID, int]:
    """How many alerts each user has had inside `RATE_WINDOW`. The rate cap's input."""
    if not user_ids:
        return {}
    result = await db.execute(
        text(
            """
            SELECT user_id, count(*) AS n
            FROM public.sent_alerts
            WHERE user_id = ANY(:user_ids)
              AND sent_at >= cast(:cutoff as timestamptz)
            GROUP BY user_id
            """
        ),
        {"user_ids": [str(uid) for uid in user_ids], "cutoff": now - RATE_WINDOW},
    )
    return {row.user_id: int(row.n) for row in result}


async def _record(
    db: AsyncSession,
    *,
    user_id: UUID,
    flag_id: UUID,
    device_id: UUID | None,
    category: AlertCategory,
    severity: float,
    message: PushMessage,
    now: datetime,
) -> bool:
    """
    Claim the right to send this alert, by writing the ledger row first.

    Returns False when the row already existed, which means another sweep — or
    another worker — got there first. `ON CONFLICT DO NOTHING` against
    `sent_alerts_one_per_user_per_flag` makes that race the database's problem
    rather than a lock's: two workers both passing the in-memory `already_sent`
    check is possible, and exactly one of them gets the insert.

    This is why the ledger is written *before* the send and not after. Afterwards
    it would be correct only as long as nothing ever crashed between the two.
    """
    result = await db.execute(
        text(
            """
            INSERT INTO public.sent_alerts (
                user_id, flag_id, device_id, category, severity_at_send,
                title, body, delivery, sent_at
            )
            VALUES (
                :user_id, :flag_id, :device_id, :category, :severity,
                :title, :body, 'queued', cast(:now as timestamptz)
            )
            ON CONFLICT (user_id, flag_id) DO NOTHING
            RETURNING id
            """
        ),
        {
            "user_id": str(user_id),
            "flag_id": str(flag_id),
            "device_id": str(device_id) if device_id else None,
            "category": category.value,
            "severity": severity,
            "title": message.title,
            "body": message.body,
            "now": now,
        },
    )
    return result.first() is not None


async def _settle(
    db: AsyncSession, *, user_id: UUID, flag_id: UUID, receipt: PushReceipt
) -> None:
    """Record what the transport actually managed to do."""
    await db.execute(
        text(
            """
            UPDATE public.sent_alerts
            SET delivery        = :delivery,
                expo_receipt_id = :receipt_id,
                error           = :error
            WHERE user_id = :user_id AND flag_id = :flag_id
            """
        ),
        {
            "user_id": str(user_id),
            "flag_id": str(flag_id),
            "delivery": "accepted" if receipt.ok else "rejected",
            "receipt_id": receipt.receipt_id,
            "error": receipt.error[:500] if receipt.error else None,
        },
    )


async def read_history(
    db: AsyncSession, *, user_id: UUID, limit: int = 50
) -> list[dict[str, Any]]:
    """
    One user's alert history, newest first.

    This is not a nicety. A rate cap and a severity threshold are invisible
    mechanisms that decide whether somebody is warned, and without a way to read
    the ledger back the only answer to "why didn't I get an alert?" is to open a
    SQL console. It is also what makes the walkthrough checkable: step 7 asserts
    that the fourth alert in an hour is absent *here*, not just absent from the
    lock screen, which is the difference between "the cap worked" and "the push
    was dropped".
    """
    result = await db.execute(
        text(
            """
            SELECT flag_id, category, severity_at_send, title, body,
                   delivery, error, sent_at
            FROM public.sent_alerts
            WHERE user_id = :user_id
            ORDER BY sent_at DESC
            LIMIT :limit
            """
        ),
        {"user_id": str(user_id), "limit": limit},
    )
    return [
        {
            "flag_id": str(row.flag_id),
            "category": row.category,
            "severity_at_send": float(row.severity_at_send),
            "title": row.title,
            "body": row.body,
            "delivery": row.delivery,
            "error": row.error,
            "sent_at": row.sent_at,
        }
        for row in result
    ]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DispatchOutcome:
    """
    What one sweep did. Becomes the `AgentResult`.

    `refusals` is a `Counter` over `Refusal` values, and it is the field worth
    having: "0 sent" is ambiguous between a broken pipeline and a quiet city, and
    `{"below_min_severity": 41}` tells them apart at a glance.
    """

    devices: int = 0
    candidates: int = 0
    sent: int = 0
    failed: int = 0
    refusals: Counter[str] = field(default_factory=Counter)


async def dispatch_for_devices(
    db: AsyncSession,
    *,
    surface: RiskSurface,
    transport: PushTransport,
    now: datetime,
    radius_m: int | None = None,
) -> DispatchOutcome:
    """
    One sweep: for every active device, alert on anything new and near it.

    The order of operations matters and is not obvious, so it is spelled out:

    1. read all active devices;
    2. read preferences and ledger state for their users **in bulk**, three
       queries total rather than three per device;
    3. per device, ask the surface what is near it;
    4. per flag, `decide()`;
    5. for each allowed alert, write the ledger row, then send;
    6. settle the row with the receipt, and disable the token if it is dead.

    Step 2 is what keeps a once-a-minute sweep cheap. Step 5's order is what
    makes a crash mid-send lose a notification rather than duplicate one.

    `sent_in_window` is incremented locally as alerts are sent, so the cap holds
    *within* a single sweep. Without that, a device sitting beside six qualifying
    flags would be sent all six — every one of them passing a cap check that read
    the same pre-sweep count. That was the first version of this loop and it is
    the exact shape of the bug the cap exists to prevent.
    """
    outcome = DispatchOutcome()
    devices = await _active_devices(db, now=now)
    outcome.devices = len(devices)
    if not devices:
        return outcome

    user_ids = sorted({device.user_id for device in devices})
    prefs_by_user = await load_preferences(db, user_ids)
    alerted = await _alerted_flag_ids(db, user_ids)
    sent_counts = await _sent_in_window(db, user_ids, now=now)

    corridor_radius = radius_m if radius_m is not None else settings.ALERT_RADIUS_M

    for device in devices:
        prefs = prefs_by_user.get(device.user_id, AlertPreferences())
        already = alerted.setdefault(device.user_id, set())

        flags: list[RiskFlag] = await surface.flags_near(
            device.lat, device.lon, corridor_radius, now
        )
        outcome.candidates += len(flags)

        # Every decision for this device, made up front, with the cap applied
        # across the batch rather than per flag. See `plan_for_device` for the
        # bug that shape prevents -- it is the one the cap exists to stop and it
        # is invisible in a log.
        plan = plan_for_device(
            flags=flags,
            prefs=prefs,
            already_alerted_flag_ids=frozenset(already),
            sent_in_window=sent_counts.get(device.user_id, 0),
            system_cap=settings.MAX_ALERTS_PER_USER_PER_HOUR,
            at=now,
        )
        outcome.refusals.update(plan.refusals)

        for flag, verdict in plan.sends:
            message = compose_alert(
                flag=flag, category=verdict.category, severity=verdict.severity
            )
            claimed = await _record(
                db,
                user_id=device.user_id,
                flag_id=flag.flag_id,
                device_id=device.id,
                category=verdict.category,
                severity=verdict.severity,
                message=message,
                now=now,
            )
            # The plan already treated this flag as spent, so the counters move
            # whatever the claim says. `already` keeps the next device belonging
            # to the same user from reconsidering it, and `sent_counts` keeps the
            # cap honest across devices.
            already.add(flag.flag_id)
            sent_counts[device.user_id] = sent_counts.get(device.user_id, 0) + 1

            if not claimed:
                # Another sweep or worker inserted the ledger row first. Letting
                # it count against the cap over-counts by one in a rare race,
                # which is the cheaper error -- see `_record`.
                outcome.refusals["already_sent"] += 1
                continue

            receipt = (await transport.send([(device.expo_push_token, message)]))[0]
            await _settle(db, user_id=device.user_id, flag_id=flag.flag_id, receipt=receipt)
            if receipt.ok:
                outcome.sent += 1
            else:
                outcome.failed += 1
                logger.warning(
                    "push rejected for device %s: %s", device.id, receipt.error
                )
            if receipt.device_gone:
                await _disable_device(
                    db,
                    token=device.expo_push_token,
                    reason=receipt.error or "DeviceNotRegistered",
                    now=now,
                )
                break  # Nothing else will reach this device this sweep.

        await db.commit()

    return outcome


async def send_test_alert(
    db: AsyncSession,
    *,
    user_id: UUID,
    transport: PushTransport,
    now: datetime,
) -> dict[str, Any]:
    """
    Push a test notification to every one of this user's live devices.

    It respects the rate cap. That is a deliberate and mildly annoying choice:
    the cap is the thing S16 asks to be proven, and an endpoint that bypassed it
    would be the one way to demonstrate the system while sidestepping its most
    important rule. A tester who hits the cap has just observed it working, which
    is why the response says so explicitly rather than reporting a bare failure.

    Each send invents a fresh `flag_id`, so repeated tests do not collide with
    the one-alert-per-flag constraint. This is the reason `sent_alerts.flag_id`
    has no foreign key — see the migration.
    """
    devices = (
        await db.execute(
            text(
                """
                SELECT id, expo_push_token
                FROM public.push_devices
                WHERE user_id = :user_id AND disabled_at IS NULL
                """
            ),
            {"user_id": str(user_id)},
        )
    ).all()

    if not devices:
        return {
            "sent": 0,
            "devices": 0,
            "detail": (
                "No registered device. Open the app, allow notifications, and let it "
                "register — then try again."
            ),
        }

    cap = (await load_preferences(db, [user_id])).get(user_id, AlertPreferences()).effective_cap(
        settings.MAX_ALERTS_PER_USER_PER_HOUR
    )
    used = (await _sent_in_window(db, [user_id], now=now)).get(user_id, 0)
    if used >= cap:
        return {
            "sent": 0,
            "devices": len(devices),
            "detail": (
                f"Rate cap reached: {used} of {cap} alerts in the last hour. This is the "
                "cap working, not a failure. Wait for the hour to roll off."
            ),
        }

    message = compose_test_alert()
    sent = 0
    for device in devices:
        flag_id = uuid4()
        if not await _record(
            db,
            user_id=user_id,
            flag_id=flag_id,
            device_id=device.id,
            category=AlertCategory.TEST,
            severity=0.0,
            message=message,
            now=now,
        ):
            continue
        receipt = (await transport.send([(device.expo_push_token, message)]))[0]
        await _settle(db, user_id=user_id, flag_id=flag_id, receipt=receipt)
        if receipt.ok:
            sent += 1
        if receipt.device_gone:
            await _disable_device(
                db,
                token=device.expo_push_token,
                reason=receipt.error or "DeviceNotRegistered",
                now=now,
            )
        # One test per call regardless of device count: sending to three devices
        # would spend three of the user's hourly slots to answer one question.
        break

    await db.commit()
    return {
        "sent": sent,
        "devices": len(devices),
        "detail": (
            "Queued with Expo."
            if sent
            else "Expo rejected the message — check PUSH_ENABLED and the EAS credentials."
        ),
    }
