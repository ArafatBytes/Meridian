"""
Crime report model
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.core.database import Base
from app.models.columns import UUIDStr


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
    
    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUIDStr, ForeignKey("users.id"), nullable=False)
    # `values_callable` is load-bearing, not a style choice. Without it
    # SQLAlchemy maps this column by the enum's *member names* (THEFT, ASSAULT)
    # while every row in the database holds its *value* ('theft', 'assault') --
    # the frontend writes reports straight to Supabase, in lowercase, and the
    # Postgres enum's labels are lowercase too. Reading any existing report
    # through the ORM then raises
    #   LookupError: 'other' is not among the defined enum values
    # which stayed invisible until D08 became the first code to read a report
    # back through SQLAlchemy at all (the handlers in endpoints/crimes.py are
    # still stubs).
    category = Column(
        SQLEnum(
            CrimeCategory,
            name="crime_category",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
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
