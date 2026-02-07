"""
Dompet Curhat - AI-Powered Emotional Expense Tracker
Main FastAPI Application

A chat-based expense tracker that listens to your financial stories,
extracts transaction data automatically, and responds with empathy.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
import os

from config import settings
from routes import chat_router, expense_router, upload_router, report_router, auth_router, dashboard_router, get_current_user


# Initialize FastAPI app
app = FastAPI(
    title="SIBudget",
    description="AI-Powered Emotional Expense Tracker - Your financial diary that listens",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware for frontend
allowed_origins_list = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# Include API routers
app.include_router(chat_router)
app.include_router(expense_router)
app.include_router(upload_router)
app.include_router(report_router)
app.include_router(auth_router)
app.include_router(dashboard_router)



# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with user-friendly messages."""
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = error.get("loc", ["", ""])[-1]
        error_type = error.get("type", "")
        
        # Translate common validation errors to Indonesian
        if "email" in str(field).lower():
            error_messages.append("Format email tidak valid")
        elif "password" in str(field).lower():
            if "min_length" in error_type:
                error_messages.append("Password minimal 6 karakter")
            else:
                error_messages.append("Password tidak valid")
        elif "full_name" in str(field).lower() or "name" in str(field).lower():
            if "min_length" in error_type:
                error_messages.append("Nama minimal 2 karakter")
            else:
                error_messages.append("Nama tidak valid")
        else:
            error_messages.append(f"Field {field} tidak valid")
    
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(error_messages) if error_messages else "Data tidak valid"}
    )

# ==================== AUTH PAGE ROUTES ====================

@app.get("/login")
async def login_page(request: Request, error: str = None):
    """Login page."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Login - SIBudget", "error": error}
    )


@app.get("/register")
async def register_page(request: Request):
    """Register page."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "title": "Register - SIBudget"}
    )


# ==================== PAGE ROUTES ====================

@app.get("/")
async def home(request: Request):
    """Main dashboard interface."""
    user = await get_current_user(request)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Dashboard - SIBudget", "user": user}
    )


@app.get("/chat")
async def chat(request: Request):
    """Main chat interface."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "chat.html",
        {"request": request, "title": "Chat - SIBudget", "user": user}
    )


@app.get("/insight")
async def insight(request: Request):
    """Dashboard and insights page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "insight.html",
        {"request": request, "title": "Insight - SIBudget", "user": user}
    )


# ==================== HEALTH CHECK ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "SIBudget",
        "version": "1.0.0"
    }


# ==================== STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("🚀 SIBudget starting up...")
    if settings.debug:
        print(f"📊 Debug mode: {settings.debug}")
        print(f"🤖 Accountant Model: {settings.accountant_model}")
        print(f"💬 Bestie Model: {settings.bestie_model}")
        print(f"👁️ Scanner Model: {settings.scanner_model}")
    else:
        print("🔒 Running in production mode")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("👋 SIBudget shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
