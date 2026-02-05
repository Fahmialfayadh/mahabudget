"""Pydantic models for expense data."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class EmotionLabel(str, Enum):
    """Supported emotion labels for expense tagging."""
    MARAH = "Marah"
    SEDIH = "Sedih"
    SENANG = "Senang"
    LAPAR = "Lapar"
    STRESS = "Stress"
    NETRAL = "Netral"


class ExpenseCategory(str, Enum):
    """Expense categories for classification."""
    MAKANAN_MINUMAN = "Makanan & Minuman"
    TRANSPORT = "Transport"
    FASHION = "Fashion"
    HIBURAN = "Hiburan"
    BELANJA = "Belanja"
    TAGIHAN = "Tagihan"
    LAINNYA = "Lainnya"


class ExpenseExtraction(BaseModel):
    """Data extracted from user's informal expense message."""
    item_name: str = Field(..., description="Name of the item purchased")
    amount: int = Field(..., ge=0, description="Amount in IDR")
    category: ExpenseCategory = Field(default=ExpenseCategory.LAINNYA)
    emotion: EmotionLabel = Field(default=EmotionLabel.NETRAL)
    sentiment_score: float = Field(
        default=0.0, 
        ge=-1.0, 
        le=1.0, 
        description="Sentiment from -1.0 (negative) to 1.0 (positive)"
    )
    ai_confidence: float = Field(
        default=0.8, 
        ge=0.0, 
        le=1.0, 
        description="AI confidence in extraction accuracy"
    )


class ExpenseCreate(BaseModel):
    """Schema for creating a new expense."""
    user_id: int
    item_name: str
    description: Optional[str] = None
    amount: int = Field(..., ge=0)
    category: str
    emotion_label: str
    sentiment_score: float = 0.0
    ai_confidence: float = 1.0  # Default 1.0 for manual input
    receipt_url: Optional[str] = None
    is_regret: Optional[bool] = None # New field
    date: Optional[datetime] = None # For manual input


class ExpenseManualCreate(BaseModel):
    """Schema for manually creating a new expense."""
    item_name: str
    amount: int = Field(..., ge=0)
    category: str
    emotion_label: str
    date: Optional[datetime] = None
    is_regret: Optional[bool] = None


class ExpenseResponse(BaseModel):
    """Schema for expense response from database."""
    id: int
    user_id: int
    date: datetime
    item_name: str
    description: Optional[str]
    amount: int
    category: str
    sentiment_score: Optional[float]
    emotion_label: Optional[str]
    ai_confidence: Optional[float]
    receipt_url: Optional[str]
    is_regret: Optional[bool] # New field


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense (correction mode or audit)."""
    item_name: Optional[str] = None
    amount: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    emotion_label: Optional[str] = None
    description: Optional[str] = None
    is_regret: Optional[bool] = None # New field
    date: Optional[datetime] = None
