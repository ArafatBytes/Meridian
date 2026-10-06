"""
API v1 router aggregation
"""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, crimes, routes, tracking, sos, users, ai, voice

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(crimes.router, prefix="/crimes", tags=["Crime Reports"])
api_router.include_router(routes.router, prefix="/routes", tags=["Routing"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["Location Tracking"])
api_router.include_router(sos.router, prefix="/sos", tags=["SOS Emergency"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice Analysis"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI & Machine Learning"])
