"""
SOS Emergency endpoints
"""
import json
import logging
from sqlalchemy import select, text
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, Final
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.sos import (
    SOSTriggerRequest,
    SOSResponse,
    SOSHistoryEntry,
    SOSHistoryResponse,
)
from app.services.sos_service import sos_service
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/trigger", status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    latitude: float = Form(...),
    longitude: float = Form(...),
    video: Optional[UploadFile] = File(None),
    # B8 / S18. Whether a hot word started this, rather than the button or the
    # shake. Defaults false, so every existing caller is unchanged.
    voice_activated: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    """
    Trigger SOS emergency
    - Get emergency contacts
    - Send email alerts with video attachment (if provided)
    - Video must be less than 25MB
    """
    try:
        # Fetch actual user object to get name
        # current_user from security is a dict {"user_id": ..., "email": ...}
        user_id = current_user["user_id"]
        result = await db.execute(select(User).where(User.id == user_id))
        user_obj = result.scalars().first()
        
        if not user_obj:
             # Auto-provision user from Supabase token details
             print(f"⚠️ User {user_id} not found in local DB. Creating now...")
             email = current_user.get("email", f"user_{user_id}@example.com")
             # Derive name from email
             name = email.split("@")[0] if "@" in email else "Meridian User"
             
             user_obj = User(
                 id=user_id,
                 email=email,
                 full_name=name,
                 phone="N/A",  # Required field
                 password_hash="supabase_managed",  # Required field
                 is_verified=True
             )
             db.add(user_obj)
             await db.flush() # Ensure ID is valid for foreign keys
             # Note: Commit happens in sos_service or via dependency cleanup? 
             # Safer to commit here to persist user.
             await db.commit()
             await db.refresh(user_obj)

        location = {
            "latitude": latitude,
            "longitude": longitude
        }

        result = await sos_service.trigger_sos_alert(
            user_id=user_obj.id,
            user_name=user_obj.full_name,
            location=location,
            video_file=video,
            db=db,
            voice_activated=voice_activated,
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )

        return {
            "message": result["message"],
            "contacts_notified": result["contacts_notified"],
            "video_attached": result.get("video_attached", False),
            "location": location,
            # Defect 35: the id of the row now written to sos_incidents. None
            # means the alert went out but the audit write failed, which is worth
            # being able to tell apart from the alert itself failing.
            "incident_id": result.get("incident_id"),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ SOS TRIGGER ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger SOS: {str(e)}"
        )


# ---------------------------------------------------------------------------
# D09 — "the alert was delivered, and here is the record"
# ---------------------------------------------------------------------------

# Raw SQL for one reason: `location` is a PostGIS geography, and reading it through
# the ORM hands back WKB that then needs decoding. `ST_Y`/`ST_X` in the query is
# what `scoring/surface_db.py` already does, and `extensions` is the schema PostGIS
# lives in on this Supabase project.
_HISTORY: Final = text(
    """
    select id, timestamp, status, voice_activated, contacts_notified,
           extensions.ST_Y(location::extensions.geometry) as lat,
           extensions.ST_X(location::extensions.geometry) as lon
    from public.sos_incidents
    where user_id = :user_id
    order by timestamp desc
    limit :limit
    """
)


def _entry(row: Any) -> SOSHistoryEntry:
    """
    One row to one history entry, tolerating every shape `contacts_notified` has had.

    Three shapes exist in this column. Rows written since defect 35 hold the JSON
    object the schema documents. Rows older than it hold null. And nothing stops a
    future writer putting a bare list there, which is what the column's name
    suggests. All three have to render, because an audit trail that fails to display
    its own oldest rows is not much of an audit trail — so an unreadable blob
    degrades to "delivered: not recorded" rather than to a 500.
    """
    blob: dict[str, Any] = {}
    if row.contacts_notified:
        try:
            parsed = json.loads(row.contacts_notified)
            if isinstance(parsed, dict):
                blob = parsed
        except (ValueError, TypeError):
            logger.warning("sos_incident %s has unparseable contacts_notified", row.id)

    return SOSHistoryEntry(
        id=str(row.id),
        timestamp=row.timestamp,
        latitude=float(row.lat),
        longitude=float(row.lon),
        status=row.status or "active",
        voice_activated=bool(row.voice_activated),
        delivered=blob.get("delivered"),
        recipient_count=int(blob.get("recipient_count") or 0),
        police_station_count=int(blob.get("police_station_count") or 0),
        video_attached=bool(blob.get("video_attached")),
    )


@router.get("/history", response_model=SOSHistoryResponse)
async def sos_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> SOSHistoryResponse:
    """
    This user's own past SOS alerts, most recent first.

    **Scoped to the caller by `user_id` in the WHERE clause, not by a filter applied
    afterwards.** An SOS record says where somebody was at a moment they were
    frightened; there is no route to anyone else's.

    `user_id` is the Supabase JWT's `sub`, which is exactly the value
    `trigger_sos` writes, so this matches without any mapping. The column's foreign
    key points at the `public.users` mirror rather than at `auth.users` — real debt,
    owned by ADR 0003 — but the *value* is the auth user id either way, which is why
    this needed no migration.

    No empty-list special case: zero alerts is a count of zero, and the screen says
    so in words. A 404 would mean "no such thing as your history", which is wrong.
    """
    rows = await db.execute(
        _HISTORY,
        {"user_id": current_user["user_id"], "limit": max(1, min(limit, 200))},
    )
    incidents = [_entry(row) for row in rows]
    return SOSHistoryResponse(count=len(incidents), incidents=incidents)
