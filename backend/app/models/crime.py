"""
Crime report model
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.core.database import Base


class CrimeCategory(str, enum.Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    HARASSMENT = "harassment"
    VANDALISM = "vandalism"
    BURGLARY = "burglary"
    ROBBERY = "robbery"
    FRAUD = "fraud"
    OTHER = "other"


class CrimeSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CrimeReport(Base):
    __tablename__ = "crime_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    category = Column(SQLEnum(CrimeCategory), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    incident_date_time = Column(DateTime, nullable=False, index=True)
    latitude = Column(String, nullable=False)
    longitude = Column(String, nullable=False)
    location_name = Column(String, nullable=True)
    status = Column(String, default='pending')  # pending, verified, investigating, resolved
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="crime_reports")
