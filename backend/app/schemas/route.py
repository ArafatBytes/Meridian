"""
Route calculation schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    source: Location
    destination: Location
    avoid_high_crime_zones: bool = True
    max_crime_score: Optional[int] = 75  # Don't route through zones above this score


class RouteSegment(BaseModel):
    latitude: float
    longitude: float
    crime_score: float


class RouteResponse(BaseModel):
    route_id: str
    path: List[RouteSegment]
    distance_km: float
    duration_minutes: int
    safety_score: float  # 0-100, higher is safer
    composite_score: float  # Weighted score of distance and safety
    crime_hotspots: List[Location]  # High-crime areas along the route
    
    class Config:
        from_attributes = True
