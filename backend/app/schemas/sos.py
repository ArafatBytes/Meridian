"""
SOS Emergency schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SOSTriggerRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    voice_activated: bool = False


class PoliceStationResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float
    phone: str
    address: str


class SOSResponse(BaseModel):
    incident_id: str
    timestamp: datetime
    location: dict
    nearest_police_station: PoliceStationResponse
    contacts_notified: List[str]
    video_upload_url: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True
