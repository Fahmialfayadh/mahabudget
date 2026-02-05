"""Routes package for Dompet Curhat."""

from .chat import router as chat_router
from .expense import router as expense_router
from .upload import router as upload_router
from .report import router as report_router
from .auth import router as auth_router, get_current_user, require_auth
from .dashboard import router as dashboard_router

__all__ = [
    "chat_router",
    "expense_router",
    "upload_router",
    "report_router",
    "auth_router",
    "dashboard_router",
    "get_current_user",
    "require_auth",
]

