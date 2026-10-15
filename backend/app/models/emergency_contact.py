"""
Emergency contact model
"""
from sqlalchemy import Column, String
import uuid
from app.core.database import Base
from app.models.columns import UUIDStr


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    
    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Defect 9: no ForeignKey. The real constraint is in SCHEMA.sql and targets
    # `auth.users(id)`, a schema this metadata does not map. See `models/crime.py`.
    user_id = Column(UUIDStr, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    relationship = Column(String)
    
    # No `user` relationship -- see `models/crime.py`. Defect 9.
