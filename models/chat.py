"""Pydantic models for chat functionality."""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime


class ChatMessage(BaseModel):
    """Single chat message in conversation."""
    role: Literal["user", "assistant"] = Field(..., description="Who sent the message")
    content: str = Field(..., description="Message content")
    transaction_id: Optional[int] = Field(
        default=None, 
        description="Associated expense transaction ID if applicable"
    )


class ChatMessageCreate(BaseModel):
    """Schema for saving a chat message to database."""
    user_id: int
    role: str
    content: str
    type: str = "text"  # text, receipt, confirmation, expense, review
    transaction_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    """Schema for chat message from database."""
    id: int
    user_id: int
    role: str
    content: str
    type: str
    transaction_id: Optional[int]
    date: datetime


class ChatRequest(BaseModel):
    """Incoming chat request from user."""
    user_id: int
    message: str


class ExpenseDataItem(BaseModel):
    """Single expense item in response."""
    item_name: str
    amount: int
    category: str
    emotion: str
    sentiment_score: float
    ai_confidence: float


class ChatResponse(BaseModel):
    """Response to user chat - supports multiple expenses."""
    message: str
    expense_saved: bool = False
    expenses_count: int = 0  # How many expenses were saved
    expense_data: Optional[List[dict]] = None  # List of expenses (can be single or multiple)
    requires_confirmation: bool = False

