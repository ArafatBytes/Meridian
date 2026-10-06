"""
Emergency contact model
"""
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship as sa_relationship
import uuid
from app.core.database import Base


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String, nullable=False)
    relationship = Column(String)
    
    # Relationships
    user = sa_relationship("User", back_populates="emergency_contacts")
