"""Pydantic models for user data."""

from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response (without password)."""
    id: int
    username: str


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str
