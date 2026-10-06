"""
SOS Emergency endpoints
"""
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.sos import SOSTriggerRequest, SOSResponse
from app.services.sos_service import sos_service
from app.models.user import User

router = APIRouter()


@router.post("/trigger", status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    latitude: float = Form(...),
    longitude: float = Form(...),
    video: Optional[UploadFile] = File(None),
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
            db=db
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
            "location": location
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
