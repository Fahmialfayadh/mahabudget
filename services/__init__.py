"""Services package for Dompet Curhat."""

from .supabase_client import supabase_service
from .accountant import extract_expense_data, extract_multiple_expenses, validate_extraction
from .bestie import (
    generate_response,
    generate_confirmation_message,
    generate_monthly_narrative,
)
from .scanner import (
    read_receipt_from_url,
    read_receipt_from_base64,
    format_for_confirmation,
    compress_image,
    image_to_base64,
    ReceiptData,
)
from .auth_service import AuthService

# Initialize auth service with supabase client
auth_service = AuthService(supabase_service)

__all__ = [
    # Supabase
    "supabase_service",
    # Auth
    "auth_service",
    "AuthService",
    # Accountant
    "extract_expense_data",
    "extract_multiple_expenses",
    "validate_extraction",
    # Bestie
    "generate_response",
    "generate_confirmation_message",
    "generate_monthly_narrative",
    # Scanner
    "read_receipt_from_url",
    "read_receipt_from_base64",
    "format_for_confirmation",
    "compress_image",
    "image_to_base64",
    "ReceiptData",
]
