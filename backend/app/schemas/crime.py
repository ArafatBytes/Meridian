"""
Crime report schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CrimeCategory(str, Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    HARASSMENT = "harassment"
    VANDALISM = "vandalism"
    BURGLARY = "burglary"
    ROBBERY = "robbery"
    FRAUD = "fraud"
    OTHER = "other"


class CrimeReportCreate(BaseModel):
    category: CrimeCategory
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    incident_date_time: datetime
    latitude: str
    longitude: str
    location_name: Optional[str] = None


class CrimeReportResponse(BaseModel):
    id: str
    category: CrimeCategory
    title: str
    description: str
    incident_date_time: datetime
    latitude: str
    longitude: str
    location_name: Optional[str]
    status: str
    verified: bool
    created_at: datetime
    user_id: str
    
    class Config:
        from_attributes = True


class CrimeHeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: float  # 0-100


class CrimeHeatmapResponse(BaseModel):
    points: List[CrimeHeatmapPoint]
    total_crimes: int
