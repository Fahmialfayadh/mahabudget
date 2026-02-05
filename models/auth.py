"""Pydantic models for authentication."""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserInsightCreate(BaseModel):
    """Schema for creating a new user in users_insight."""
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)


class UserInsightLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserInsightResponse(BaseModel):
    """Schema for user response (without password)."""
    id: int
    email: str
    full_name: str
    is_admin: bool = False
    profile_picture: Optional[str] = None
    oauth_provider: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInsightResponse


class GoogleUserInfo(BaseModel):
    """Schema for Google OAuth user info."""
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    verified_email: bool = True


class RefreshTokenCreate(BaseModel):
    """Schema for creating refresh token record."""
    user_id: int
    token_hash: str
    expires_at: datetime
    device_info: Optional[str] = None


class UserExpenseSync(BaseModel):
    """Schema for user expense synchronization."""
    user_insight_id: int
    legacy_user_id: Optional[int] = None
