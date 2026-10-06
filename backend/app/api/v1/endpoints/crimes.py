"""
Crime report endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.crime import CrimeReportCreate, CrimeReportResponse, CrimeHeatmapResponse

router = APIRouter()


@router.post("/report", response_model=CrimeReportResponse, status_code=status.HTTP_201_CREATED)
async def report_crime(
    report: CrimeReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Submit a new crime report"""
    # TODO: Implement crime report creation
    pass


@router.get("/nearby", response_model=List[CrimeReportResponse])
async def get_nearby_crimes(
    lat: float,
    lng: float,
    radius: int = 1000,  # meters
    db: AsyncSession = Depends(get_db)
):
    """Get nearby crime reports"""
    # TODO: Implement geospatial query for nearby crimes
    pass


@router.get("/heatmap", response_model=CrimeHeatmapResponse)
async def get_crime_heatmap(
    lat: float,
    lng: float,
    radius: int = 5000,
    db: AsyncSession = Depends(get_db)
):
    """Get crime heatmap data"""
    # TODO: Implement heatmap generation
    pass


@router.post("/{crime_id}/verify", status_code=status.HTTP_200_OK)
async def verify_crime_report(
    crime_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Verify a crime report (admin only)"""
    # TODO: Implement crime verification
    pass
