"""
API v1 router aggregation

`/voice` is gone, removed in B8. `endpoints/voice.py` held one route,
`POST /voice/analyze`, and it was a stub that could never return true: it ignored
the caller's stored `sos_hot_words` in favour of a hardcoded list, set
`transcript = ""` with a `# TODO: Implement actual speech recognition`, and then
reported `trigger: false` for every request. Nothing in the app ever called it.

S18 gave the choice in one line — *"`/voice/analyze` either works against real
hot words or is removed"* — and removal is the right half, because hot-word
matching now happens **on the device** (`frontend/src/features/voice/`). An
endpoint for it would mean uploading audio, which is the thing S18's privacy bar
exists to prevent. Deleting it also deletes an unauthenticated-looking upload
surface that nothing was watching.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    auth,
    casework,
    crimes,
    geo,
    ingestion,
    notifications,
    risk,
    routes,
    sos,
    tracking,
    users,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(crimes.router, prefix="/crimes", tags=["Crime Reports"])
api_router.include_router(routes.router, prefix="/routes", tags=["Routing"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Surface"])
api_router.include_router(geo.router, prefix="/geo", tags=["Place Resolution"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Live News Ingestion"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["Location Tracking"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["Notifications"]
)
api_router.include_router(sos.router, prefix="/sos", tags=["SOS Emergency"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI & Machine Learning"])
api_router.include_router(casework.router, prefix="/casework", tags=["Casework — General Diary"])
