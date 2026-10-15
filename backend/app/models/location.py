"""
User location tracking model
"""
from sqlalchemy import Column, String, DateTime, Float
from geoalchemy2 import Geography
from datetime import datetime
import uuid
from app.core.database import Base
from app.models.columns import UUIDStr


class UserLocation(Base):
    __tablename__ = "user_locations"
    
    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Defect 9: no ForeignKey. The real constraint is in SCHEMA.sql and targets
    # `auth.users(id)`, a schema this metadata does not map. See `models/crime.py`.
    user_id = Column(UUIDStr, nullable=False)
    location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    accuracy = Column(Float)  # meters
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # No `user` relationship -- see `models/crime.py`. Defect 9.
