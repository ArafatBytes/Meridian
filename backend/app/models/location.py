"""
User location tracking model
"""
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid
from app.core.database import Base


class UserLocation(Base):
    __tablename__ = "user_locations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    accuracy = Column(Float)  # meters
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="location_history")
