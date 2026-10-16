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
    agents,
    ai,
    casework,
    geo,
    ingestion,
    journeys,
    notifications,
    risk,
    routes,
    sos,
)

api_router = APIRouter()

# There is no `/auth` router, and there must not be one. ADR 0002: Supabase Auth
# is the only identity provider and this backend verifies tokens without being
# able to issue them.
#
# `endpoints/auth.py` was deleted on 15 Oct. It was not a stub — `/auth/login`
# and `/auth/register` were live, unauthenticated, and returned a *signed,
# accepted* token for any email posted to them, with `verify_password` imported
# and never called. Measured end to end before removal: the forged token reached
# `get_current_user`, which returned a principal, which made every endpoint
# behind that dependency reachable without credentials. See ADR 0002's finding.
#
# The client never called it. `api.service.ts` refreshes through
# `supabase.auth.refreshSession()` and its comment already said `/auth/refresh`
# was a stub that "would have 422'd even if it were implemented".
#
# `/users`, `/crimes` and `/tracking` are gone too, deleted the same day under
# ADR 0001. Every operation they named — read my profile, add an emergency
# contact, file a report, update my location — is **user-owned CRUD**, which that
# ADR puts on the Supabase-direct plane under RLS, and which the client has been
# doing directly all along: `profiles`, `emergency_contacts`, `sos_hot_words` and
# `crime_reports`.
#
# Every one of their handlers was a bare `pass`. That is not a harmless
# placeholder in a registered route: `pass` returns `None`, and `None` against a
# non-optional `response_model` is a **500**, so the API advertised
# `POST /api/v1/crimes/report` and failed in a way that reads like the caller's
# bug. Defect 56 was exactly this shape — a registered endpoint nobody called,
# unexamined for months — which is why these went immediately after it rather
# than waiting for a cleanup sprint.
#
# Their schemas went with them: `schemas/user.py`, `schemas/crime.py`,
# `schemas/tracking.py` had no other importer, and a schema describing an
# endpoint that does not exist is the template for recreating it.

# Include all endpoint routers
api_router.include_router(routes.router, prefix="/routes", tags=["Routing"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Surface"])
api_router.include_router(geo.router, prefix="/geo", tags=["Place Resolution"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Live News Ingestion"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["Notifications"]
)
api_router.include_router(sos.router, prefix="/sos", tags=["SOS Emergency"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI & Machine Learning"])
api_router.include_router(casework.router, prefix="/casework", tags=["Casework — General Diary"])
# B9. Registered by hand like every other router above, and that is the point:
# B3 proposed replacing this list with a loader that publishes whatever it finds
# in `endpoints/`, and that row was skipped partly because of this file. Defect
# 56 was a registered route nobody had decided to publish. Adding a line here is
# the decision.
api_router.include_router(agents.router, prefix="/agents", tags=["Agent Fleet Status"])
api_router.include_router(journeys.router, prefix="/journeys", tags=["Journey Guardian"])
