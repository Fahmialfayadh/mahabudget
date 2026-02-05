"""
Authentication routes for login, register, and OAuth.
"""

from fastapi import APIRouter, HTTPException, Response, Request, Depends
from fastapi.responses import RedirectResponse
from typing import Optional
import secrets

from config import settings
from models import (
    UserInsightCreate,
    UserInsightLogin,
    UserInsightResponse,
    TokenResponse,
)
from services import auth_service


router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Cookie settings
COOKIE_SETTINGS = {
    "httponly": True,
    "secure": not settings.debug,  # Secure in production
    "samesite": "lax",
}


def set_auth_cookies(
    response: Response, 
    access_token: str, 
    refresh_token: str, 
    user_id: int
) -> None:
    """Set authentication cookies on response."""
    # Access token (short-lived)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **COOKIE_SETTINGS
    )
    
    # Refresh token (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        **COOKIE_SETTINGS
    )
    
    # User ID (accessible by JS for UI purposes)
    response.set_cookie(
        key="user_id",
        value=str(user_id),
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        httponly=False,
        secure=not settings.debug,
        samesite="lax",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear all authentication cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("user_id")


async def get_current_user(request: Request) -> Optional[UserInsightResponse]:
    """Dependency to get current authenticated user from cookies."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None
    
    payload = auth_service.verify_access_token(access_token)
    if not payload:
        return None
    
    user_id = int(payload.get("sub", 0))
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        return None
    
    return auth_service.to_user_response(user)


async def require_auth(request: Request) -> UserInsightResponse:
    """Dependency that requires authentication."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ==================== REGISTER ====================

@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserInsightCreate,
    response: Response,
    request: Request
):
    """Register a new user with email and password."""
    try:
        # Check if email already exists
        existing_user = await auth_service.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="Email sudah terdaftar"
            )
        
        # Create user
        user = await auth_service.create_user(user_data)
        if not user:
            raise HTTPException(
                status_code=500, 
                detail="Gagal membuat akun. Silakan coba lagi."
            )
        
        # Generate tokens
        access_token = auth_service.create_access_token(user["id"], user["email"])
        refresh_token = auth_service.create_refresh_token()
        
        # Store refresh token
        device_info = request.headers.get("User-Agent", "")[:200]
        await auth_service.store_refresh_token(user["id"], refresh_token, device_info)
        
        # Set cookies
        set_auth_cookies(response, access_token, refresh_token, user["id"])
        
        # Update last login
        await auth_service.update_last_login(user["id"])
        
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=auth_service.to_user_response(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan: {str(e)}"
        )


# ==================== LOGIN ====================

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserInsightLogin,
    response: Response,
    request: Request
):
    """Login with email and password."""
    # Get user
    user = await auth_service.get_user_by_email(credentials.email)
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Email atau password salah"
        )
    
    # Check if user has password (not OAuth-only)
    if not user.get("password_hash"):
        raise HTTPException(
            status_code=401, 
            detail="Akun ini menggunakan Google. Silakan login dengan Google."
        )
    
    # Verify password
    if not auth_service.verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=401, 
            detail="Email atau password salah"
        )
    
    # Generate tokens
    access_token = auth_service.create_access_token(user["id"], user["email"])
    refresh_token = auth_service.create_refresh_token()
    
    # Store refresh token
    device_info = request.headers.get("User-Agent", "")[:200]
    await auth_service.store_refresh_token(user["id"], refresh_token, device_info)
    
    # Set cookies
    set_auth_cookies(response, access_token, refresh_token, user["id"])
    
    # Update last login
    await auth_service.update_last_login(user["id"])
    
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=auth_service.to_user_response(user)
    )


# ==================== LOGOUT ====================

@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and revoke tokens."""
    refresh_token = request.cookies.get("refresh_token")
    access_token = request.cookies.get("access_token")
    
    if access_token:
        payload = auth_service.verify_access_token(access_token)
        if payload and refresh_token:
            user_id = int(payload.get("sub", 0))
            await auth_service.revoke_refresh_token(refresh_token, user_id)
    
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


# ==================== REFRESH TOKEN ====================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response):
    """Refresh access token using refresh token."""
    refresh_token_value = request.cookies.get("refresh_token")
    user_id_cookie = request.cookies.get("user_id")
    
    if not refresh_token_value or not user_id_cookie:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    try:
        user_id = int(user_id_cookie)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID")
    
    # Verify refresh token
    is_valid = await auth_service.verify_refresh_token(refresh_token_value, user_id)
    if not is_valid:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Get user
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="User not found")
    
    # Revoke old refresh token
    await auth_service.revoke_refresh_token(refresh_token_value, user_id)
    
    # Generate new tokens
    new_access_token = auth_service.create_access_token(user["id"], user["email"])
    new_refresh_token = auth_service.create_refresh_token()
    
    # Store new refresh token
    device_info = request.headers.get("User-Agent", "")[:200]
    await auth_service.store_refresh_token(user["id"], new_refresh_token, device_info)
    
    # Set new cookies
    set_auth_cookies(response, new_access_token, new_refresh_token, user["id"])
    
    return TokenResponse(
        access_token=new_access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=auth_service.to_user_response(user)
    )


# ==================== GET CURRENT USER ====================

@router.get("/me", response_model=UserInsightResponse)
async def get_me(user: UserInsightResponse = Depends(require_auth)):
    """Get current authenticated user info."""
    return user


@router.get("/status")
async def auth_status(request: Request):
    """Check authentication status."""
    user = await get_current_user(request)
    if user:
        return {
            "authenticated": True,
            "user": user.model_dump()
        }
    return {"authenticated": False}


# ==================== GOOGLE OAUTH ====================

@router.get("/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=503, 
            detail="Google OAuth not configured"
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Store state in session (using cookie for simplicity)
    auth_url = auth_service.get_google_auth_url(state)
    
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        max_age=600,  # 10 minutes
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: str = None,
    state: str = None,
    error: str = None
):
    """Handle Google OAuth callback."""
    if error:
        return RedirectResponse(url="/login?error=google_denied")
    
    if not code:
        return RedirectResponse(url="/login?error=no_code")
    
    # Verify state
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/login?error=invalid_state")
    
    # Exchange code for tokens
    tokens = await auth_service.exchange_google_code(code)
    if not tokens:
        return RedirectResponse(url="/login?error=token_exchange_failed")
    
    # Get user info from Google
    google_user = await auth_service.get_google_user_info(tokens["access_token"])
    if not google_user:
        return RedirectResponse(url="/login?error=user_info_failed")
    
    # Check if user exists by Google ID
    user = await auth_service.get_user_by_google_id(google_user.id)
    
    if not user:
        # Check if user exists by email
        user = await auth_service.get_user_by_email(google_user.email)
        if user:
            # Link Google account to existing user
            await auth_service.update_google_info(user["id"], google_user)
        else:
            # Create new user
            user = await auth_service.create_google_user(google_user)
            if not user:
                return RedirectResponse(url="/login?error=create_user_failed")
    
    # Generate our tokens
    access_token = auth_service.create_access_token(user["id"], user["email"])
    refresh_token = auth_service.create_refresh_token()
    
    # Store refresh token
    device_info = request.headers.get("User-Agent", "")[:200]
    await auth_service.store_refresh_token(user["id"], refresh_token, device_info)
    
    # Update last login
    await auth_service.update_last_login(user["id"])
    
    # Set cookies and redirect
    redirect_response = RedirectResponse(url="/")
    set_auth_cookies(redirect_response, access_token, refresh_token, user["id"])
    redirect_response.delete_cookie("oauth_state")
    
    return redirect_response
