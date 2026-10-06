"""
User schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class EmergencyContactCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    relationship: Optional[str] = None


class EmergencyContactResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: str
    relationship: Optional[str]
    
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    phone: str
    created_at: datetime
    emergency_contacts: List[EmergencyContactResponse] = []
    
    class Config:
        from_attributes = True
