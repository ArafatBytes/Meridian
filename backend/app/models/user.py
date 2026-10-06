"""
User model
"""
from sqlalchemy import Column, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hot_words = Column(JSON, default=lambda: ["help", "bachao", "save me", "police"])
    phone = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    crime_reports = relationship("CrimeReport", back_populates="user")
    emergency_contacts = relationship("EmergencyContact", back_populates="user")
    sos_incidents = relationship("SOSIncident", back_populates="user")
    location_history = relationship("UserLocation", back_populates="user")
