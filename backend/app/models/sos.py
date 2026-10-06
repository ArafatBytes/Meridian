"""
SOS incident model
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid
from app.core.database import Base


class SOSIncident(Base):
    __tablename__ = "sos_incidents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    video_url = Column(String)
    police_station_id = Column(String)
    contacts_notified = Column(Text)  # JSON string of notified contacts
    voice_activated = Column(Boolean, default=False)
    status = Column(String, default="active")  # active, resolved, false_alarm
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="sos_incidents")
