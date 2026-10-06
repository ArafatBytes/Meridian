"""
Route calculation endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.route import RouteRequest, RouteResponse
from app.services.route_service import route_service

router = APIRouter()


@router.post("/calculate", response_model=List[RouteResponse])
async def calculate_routes(
    request: RouteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate multiple route options between source and destination
    Returns routes sorted by safety-distance composite score
    """
    try:
        routes = await route_service.calculate_routes(request, db)
        return routes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate routes: {str(e)}"
        )


@router.get("/safest", response_model=RouteResponse)
async def get_safest_route(
    source_lat: float,
    source_lng: float,
    dest_lat: float,
    dest_lng: float,
    db: AsyncSession = Depends(get_db)
):
    """Get the safest route option"""
    from app.schemas.route import Location
    
    request = RouteRequest(
        source=Location(latitude=source_lat, longitude=source_lng),
        destination=Location(latitude=dest_lat, longitude=dest_lng)
    )
    
    try:
        routes = await route_service.calculate_routes(request, db)
        if not routes:
            raise HTTPException(status_code=404, detail="No safe routes found")
        # Since service returns sorted by safety, first one is safest
        return routes[0]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate routes: {str(e)}"
        )
