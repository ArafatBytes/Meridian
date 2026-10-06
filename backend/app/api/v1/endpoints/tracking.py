"""
Location tracking endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.tracking import LocationUpdate, DangerZoneAlert

router = APIRouter()


@router.post("/update-location", status_code=status.HTTP_200_OK)
async def update_location(
    location: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update user's current location"""
    # TODO: Implement location update and danger zone check
    pass


@router.get("/check-danger-zone", response_model=DangerZoneAlert)
async def check_danger_zone(
    lat: float,
    lng: float,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Check if current location is in a danger zone"""
    # TODO: Implement danger zone detection
    pass
