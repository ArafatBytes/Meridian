"""
Authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from datetime import timedelta
from app.core.config import settings

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # TODO: Implement user registration logic
    # Check if user exists, create user, generate tokens
    
    access_token = create_access_token({"sub": "user_id", "email": request.email})
    refresh_token = create_refresh_token({"sub": "user_id"})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login user"""
    # TODO: Implement login logic
    # Verify credentials, generate tokens
    
    access_token = create_access_token({"sub": "user_id", "email": request.email})
    refresh_token = create_refresh_token({"sub": "user_id"})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token"""
    # TODO: Implement token refresh logic
    pass
