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


# `POST /{crime_id}/verify` was here, as a `pass` stub labelled "admin only". It is
# GONE, not unimplemented, and the difference matters:
#
# A moderator cannot verify that a crime occurred. They can only judge whether the
# prose looks plausible, and stamping "Verified" on that judgement makes the badge
# mean "someone thought this looked fine" -- worse than no badge, because users
# will trust it. There was also no role column on `users` to gate the "admin only"
# on, so the endpoint could not have been written as specified anyway.
#
# What replaced it is corroboration, computed: several independent reports in the
# same small area inside the same window become one published cluster, with the
# thresholds in `app/policy/community.py` and the pipeline in
# `app/agents/report_corroboration.py`. Nothing approves a single report, so there
# is no endpoint for it.
#
# The human lever that remains is `status = 'removed'`, a takedown, applied through
# the service role. The asymmetry is deliberate: the machine promotes, a human only
# demotes. Nobody needs to approve a claim for it to be removed, so removal is
# exception-driven and fails in the safe direction.
#
# See migrations/versions/20261013120000__report_trust.sql.
