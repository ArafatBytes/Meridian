"""
Notification endpoints. B6a / S16.

    POST   /api/v1/notifications/devices        register or refresh this install
    DELETE /api/v1/notifications/devices        forget it (sign-out)
    GET    /api/v1/notifications/preferences    what may interrupt me
    PUT    /api/v1/notifications/preferences    change that
    POST   /api/v1/notifications/test           prove delivery works
    GET    /api/v1/notifications/history        what was sent, and what was refused
    GET    /api/v1/notifications/config         is push even switched on

Every route is scoped to the caller's `user_id` from the bearer token, never to a
value in the request body. That is the reason these tables are backend-only
rather than edited through Supabase like `emergency_contacts`: a push token is a
delivery address, and a client that could write the table could register a token
against somebody else's id and start receiving their alerts.

`GET /config` is the one that looks like debug scaffolding and is not. Remote push
has four separate prerequisites — a permission, a token, `PUSH_ENABLED`, and FCM
credentials on the EAS project — and three of them fail *silently*. Without an
endpoint that says which are satisfied, "the notification never arrived" is
indistinguishable from "the notification was never sent", and the walkthrough has
nothing to check against. It reports no secrets: a boolean per prerequisite and
the project id, which also ships inside the app bundle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.expo import default_transport
from app.alerts.policy import DEFAULT_PREFERENCES, AlertPreferences
from app.alerts.service import (
    DEVICE_LOCATION_MAX_AGE,
    count_devices,
    delete_device,
    load_preferences,
    read_history,
    register_device,
    save_preferences,
    send_test_alert,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter()


def _caller(user: dict[str, Any]) -> UUID:
    """
    The authenticated user's id, as a UUID.

    `get_current_user` returns the raw `sub` claim as a string. Parsing it here
    rather than passing the string down means a malformed token fails at the edge
    with a 401, instead of reaching a query and failing as a 500 with a Postgres
    cast error in the log.
    """
    try:
        return UUID(user["user_id"])
    except (KeyError, TypeError, ValueError) as problem:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token carries no usable user id",
        ) from problem


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

class DeviceRegistration(BaseModel):
    """
    What the app sends on every foreground.

    `lat`/`lon` are optional and that is the normal case on the first call: the
    app registers the token as soon as it has one, and reports a position
    whenever location permission yields one. Omitting them preserves whatever
    position was last known rather than clearing it.
    """

    expo_push_token: str = Field(min_length=10, max_length=255)
    platform: str = Field(pattern="^(android|ios)$")
    app_version: str | None = Field(default=None, max_length=32)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class DeviceRemoval(BaseModel):
    expo_push_token: str = Field(min_length=10, max_length=255)


class PreferencesPayload(BaseModel):
    """
    Mirrors `AlertPreferences`, with the validation the database also enforces.

    Validated in both places on purpose. The CHECK constraints are what make the
    data trustworthy; these bounds are what make a bad request a 422 naming the
    field rather than a 500 carrying a constraint name the user cannot act on.
    """

    corridor_alerts: bool = True
    scheduled_alerts: bool = True
    chronic_alerts: bool = False
    min_severity: float = Field(default=40.0, ge=0, le=100)
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)
    # Upper bound is the system cap: a value above it is silently ignored by
    # `effective_cap`, and a field that accepts a number it will not honour is a
    # worse experience than one that rejects it.
    max_per_hour: int | None = Field(default=None, ge=1)

    def to_preferences(self) -> AlertPreferences:
        return AlertPreferences(
            corridor_alerts=self.corridor_alerts,
            scheduled_alerts=self.scheduled_alerts,
            chronic_alerts=self.chronic_alerts,
            min_severity=self.min_severity,
            quiet_hours_start=self.quiet_hours_start,
            quiet_hours_end=self.quiet_hours_end,
            max_per_hour=self.max_per_hour,
        )

    @classmethod
    def of(cls, prefs: AlertPreferences) -> PreferencesPayload:
        return cls(
            corridor_alerts=prefs.corridor_alerts,
            scheduled_alerts=prefs.scheduled_alerts,
            chronic_alerts=prefs.chronic_alerts,
            min_severity=prefs.min_severity,
            quiet_hours_start=prefs.quiet_hours_start,
            quiet_hours_end=prefs.quiet_hours_end,
            max_per_hour=prefs.max_per_hour,
        )


class PreferencesResponse(BaseModel):
    """
    The user's preferences, plus the two system values they are read against.

    `system_max_per_hour` and `location_max_age_hours` are included so the screen
    can state the real rules instead of hard-coding them in TypeScript and
    drifting. The second is the honest one: it is what lets the screen say that
    alerts are based on where the app last saw you, which is the limit S17 has not
    yet lifted.
    """

    preferences: PreferencesPayload
    system_max_per_hour: int
    location_max_age_hours: float
    has_explicit_row: bool


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@router.post("/devices", status_code=status.HTTP_200_OK)
async def post_device(
    registration: DeviceRegistration,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Register or refresh this install, and optionally where it is.

    Idempotent, and called on every foreground rather than once at sign-in. Expo
    tokens rotate — on reinstall, on a restore to a new handset, occasionally on
    an OS update — and a token registered once at sign-in and never refreshed is
    the single most common way push silently stops working for a user who is
    still opening the app daily.
    """
    device_id = await register_device(
        db,
        user_id=_caller(user),
        expo_push_token=registration.expo_push_token,
        platform=registration.platform,
        app_version=registration.app_version,
        lat=registration.lat,
        lon=registration.lon,
        now=datetime.now(UTC),
    )
    return {"device_id": str(device_id), "push_enabled": settings.PUSH_ENABLED}


@router.delete("/devices", status_code=status.HTTP_200_OK)
async def remove_device(
    removal: DeviceRemoval,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Stop sending to this install. Called on sign-out.

    Returns `{"removed": false}` rather than 404 when there was nothing to
    remove. A sign-out must not fail because the token was already gone, and the
    app cannot usefully do anything differently either way.
    """
    removed = await delete_device(
        db, user_id=_caller(user), expo_push_token=removal.expo_push_token
    )
    return {"removed": removed}


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PreferencesResponse:
    """
    This user's preferences, or the defaults if they have never set any.

    `has_explicit_row` distinguishes the two, which the screen needs: "you have
    not chosen yet, here is what we do by default" is a different thing to show
    from "here is what you chose", and conflating them makes the chronic-alerts
    default look like a decision the user made.
    """
    caller = _caller(user)
    stored = await load_preferences(db, [caller])
    prefs = stored.get(caller, DEFAULT_PREFERENCES)
    return PreferencesResponse(
        preferences=PreferencesPayload.of(prefs),
        system_max_per_hour=settings.MAX_ALERTS_PER_USER_PER_HOUR,
        location_max_age_hours=DEVICE_LOCATION_MAX_AGE.total_seconds() / 3600,
        has_explicit_row=caller in stored,
    )


@router.put("/preferences", response_model=PreferencesResponse)
async def put_preferences(
    payload: PreferencesPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> PreferencesResponse:
    """Replace this user's preferences. Full replacement, not a patch."""
    if (payload.quiet_hours_start is None) != (payload.quiet_hours_end is None):
        # The database CHECK says the same thing; saying it here names the fields.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="quiet_hours_start and quiet_hours_end must both be set or both be null",
        )
    saved = await save_preferences(
        db, user_id=_caller(user), prefs=payload.to_preferences()
    )
    return PreferencesResponse(
        preferences=PreferencesPayload.of(saved),
        system_max_per_hour=settings.MAX_ALERTS_PER_USER_PER_HOUR,
        location_max_age_hours=DEVICE_LOCATION_MAX_AGE.total_seconds() / 3600,
        has_explicit_row=True,
    )


# ---------------------------------------------------------------------------
# Test send, history, config
# ---------------------------------------------------------------------------

@router.post("/test", status_code=status.HTTP_200_OK)
async def post_test(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Send this user a test notification, to prove the delivery path works.

    It counts against the rate cap, and when the cap is what stopped it the
    response says so in those words. See `send_test_alert` for why that is the
    right behaviour rather than an inconvenience: an endpoint exempt from the cap
    would be a way to demonstrate the system while bypassing its most important
    rule.
    """
    return await send_test_alert(
        db,
        user_id=_caller(user),
        transport=default_transport(dry_run=False),
        now=datetime.now(UTC),
    )


@router.get("/history", status_code=status.HTTP_200_OK)
async def get_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """
    What this user has been sent, newest first.

    The ledger read back. It is what makes an invisible mechanism checkable: a
    rate cap and a severity floor both decide whether somebody gets warned, and
    without this the only answer to "why didn't I get an alert?" is a SQL console.
    """
    return {"alerts": await read_history(db, user_id=_caller(user), limit=limit)}


@router.get("/config", status_code=status.HTTP_200_OK)
async def get_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Which prerequisites for remote push are satisfied, server-side.

    Four things have to be true before a notification arrives, and three of them
    fail quietly:

      * the user granted the notification permission      (app-side; not here)
      * the app obtained an Expo token and registered it   (`devices.active`)
      * `PUSH_ENABLED` is on                               (`push_enabled`)
      * the EAS project has FCM credentials                (**not checkable here**)

    The last one is the honest gap: only Expo knows, and it reports it per
    message rather than on demand. The nearest thing available is the error on the
    most recent rejected send, so that is returned too — it is what turns "nothing
    arrived" into a diagnosis.
    """
    caller = _caller(user)
    recent = await read_history(db, user_id=caller, limit=10)
    rejected = [row for row in recent if row["delivery"] == "rejected"]
    return {
        "push_enabled": settings.PUSH_ENABLED,
        "expo_project_id": settings.EXPO_PROJECT_ID or None,
        "max_alerts_per_hour": settings.MAX_ALERTS_PER_USER_PER_HOUR,
        "alert_radius_m": settings.ALERT_RADIUS_M,
        "location_max_age_hours": DEVICE_LOCATION_MAX_AGE.total_seconds() / 3600,
        "devices": await count_devices(db, user_id=caller),
        "last_rejection": rejected[0]["error"] if rejected else None,
    }
