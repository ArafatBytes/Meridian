"""
SOS Emergency schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SOSTriggerRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    voice_activated: bool = False


class PoliceStationResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float
    phone: str
    address: str


class SOSResponse(BaseModel):
    incident_id: str
    timestamp: datetime
    location: dict
    nearest_police_station: PoliceStationResponse
    contacts_notified: List[str]
    video_upload_url: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# D09 — the history screen
# ---------------------------------------------------------------------------


class SOSHistoryEntry(BaseModel):
    """
    One past alert, as the history screen shows it. DEMO_PLAN.md D09, beat 9.

    Flattened on purpose. `sos_incidents.contacts_notified` is a JSON *object*
    written by `sos_service._record_incident`, and every field below that is not a
    column comes out of it — so the shape of that blob stays an implementation
    detail of the service and the audit table, not something the app parses.

    `recipient_count` rather than the addresses themselves: the emails live in
    `emergency_contacts` and copying them into the audit trail would duplicate
    personal data into a second table with its own lifetime, for a screen that only
    ever needed to say "2 contacts notified".
    """

    id: str
    timestamp: datetime
    latitude: float
    longitude: float
    status: str
    voice_activated: bool

    # `delivered` is what the loop closing actually means: the alert left the
    # system. `None` on a row written before defect 35 added the blob, and the
    # screen says "not recorded" rather than guessing either way.
    delivered: Optional[bool] = None
    recipient_count: int = 0
    police_station_count: int = 0
    video_attached: bool = False


class SOSHistoryResponse(BaseModel):
    count: int
    incidents: List[SOSHistoryEntry]
