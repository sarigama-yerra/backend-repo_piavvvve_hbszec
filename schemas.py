"""
Database Schemas for Sauna & Wellness

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (e.g., Booking -> "booking").
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import date


class Service(BaseModel):
    title: str = Field(..., description="Service name")
    description: str = Field(..., description="Short description")
    duration_minutes: int = Field(..., ge=15, le=240, description="Typical duration in minutes")
    price: float = Field(..., ge=0, description="Base price in USD")
    icon: Optional[str] = Field(None, description="Icon identifier for UI")


class Membership(BaseModel):
    name: str = Field(..., description="Membership tier name")
    price_monthly: float = Field(..., ge=0)
    sessions_per_month: int = Field(..., ge=0)
    perks: List[str] = Field(default_factory=list)


class Testimonial(BaseModel):
    name: str
    quote: str
    rating: int = Field(..., ge=1, le=5)
    avatar_url: Optional[str] = None


class Newsletter(BaseModel):
    email: EmailStr


class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    message: str


class Booking(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    service: str = Field(..., description="Service title selected")
    date: date
    time: str = Field(..., description="24h format HH:MM")
    notes: Optional[str] = None


class TeamMember(BaseModel):
    name: str
    role: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
