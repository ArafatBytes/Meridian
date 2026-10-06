"""
User management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.user import UserResponse, EmergencyContactCreate, EmergencyContactResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get current user information"""
    # TODO: Implement user info retrieval
    pass


@router.put("/emergency-contacts", response_model=List[EmergencyContactResponse])
async def update_emergency_contacts(
    contacts: List[EmergencyContactCreate],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update user's emergency contacts"""
    # TODO: Implement emergency contacts update
    pass


@router.get("/emergency-contacts", response_model=List[EmergencyContactResponse])
async def get_emergency_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get user's emergency contacts"""
    # TODO: Implement emergency contacts retrieval
    pass
