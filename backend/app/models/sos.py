"""
SOS incident model
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid
from app.core.database import Base
from app.models.columns import UUIDStr


class SOSIncident(Base):
    __tablename__ = "sos_incidents"
    
    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUIDStr, ForeignKey("users.id"), nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    video_url = Column(String)
    police_station_id = Column(String)
    # JSON object, written by sos_service._record_incident (defect 35):
    #
    #   {"contact_ids": [...], "recipient_count": 2, "police_station_count": 0,
    #    "delivered": true, "video_attached": false}
    #
    # Contact ids rather than email addresses: the addresses already live in
    # emergency_contacts, and duplicating them here would put personal data in a
    # second table with its own lifetime for no benefit. D09's history screen
    # needs a count, not a list.
    contacts_notified = Column(Text)
    voice_activated = Column(Boolean, default=False)
    status = Column(String, default="active")  # active, resolved, false_alarm
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="sos_incidents")
