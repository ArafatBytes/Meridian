"""
Location tracking schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None  # meters


class DangerZoneAlert(BaseModel):
    is_danger_zone: bool
    crime_score: float
    message: Optional[str] = None
    nearest_safe_route: Optional[str] = None
