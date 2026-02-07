"""
Authentication service for users_insight database.
Handles JWT tokens, password hashing, and Google OAuth.
Uses separate Supabase connections for auth and main databases.
"""

import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import hashlib
import secrets
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

from config import settings
from models import (
    UserInsightCreate,
    UserInsightResponse,
    GoogleUserInfo,
    RefreshTokenCreate,
)


class AuthService:
    """Service for authentication operations with users_insight table."""
    
    # JWT Configuration
    ALGORITHM = "HS256"
    
    def __init__(self, main_supabase_client=None):
        """
        Initialize with dual Supabase connections.
        - auth_client: For users_insight table (separate auth database)
        - main_client: For refresh_tokens table (main SIBudget database)
        """
        # Create auth database client (for users_insight)
        self.auth_client: Client = create_client(
            settings.auth_supabase_url,
            settings.auth_supabase_service_key
        )
        
        # Use main SIBudget client for refresh_tokens
        if main_supabase_client:
            self.main_client = main_supabase_client.client
            self.main_service_client = main_supabase_client.service_client
        else:
            # Fallback: create new main client
            self.main_client = create_client(
                settings.supabase_url,
                settings.supabase_service_key
            )
    
    # ==================== PASSWORD OPERATIONS ====================
    
    def hash_password(self, password: str) -> str:
        """Hash password using werkzeug (compatible with existing system)."""
        return generate_password_hash(password)
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            return check_password_hash(password_hash, password)
        except Exception:
            return False
    
    # ==================== JWT TOKEN OPERATIONS ====================
    
    def create_access_token(self, user_id: int, email: str) -> str:
        """Create JWT access token."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(payload, settings.secret_key, algorithm=self.ALGORITHM)
    
    def create_refresh_token(self) -> str:
        """Create a secure refresh token."""
        return secrets.token_urlsafe(64)
    
    def hash_token(self, token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def verify_access_token(self, token: str) -> Optional[dict]:
        """Verify and decode access token."""
        try:
            payload = jwt.decode(
                token, 
                settings.secret_key, 
                algorithms=[self.ALGORITHM]
            )
            if payload.get("type") != "access":
                return None
            return payload
        except JWTError:
            return None
    
    # ==================== USER OPERATIONS (users_insight) ====================
    
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user from users_insight by email (auth database)."""
        try:
            response = self.auth_client.table("users_insight") \
                .select("*") \
                .eq("email", email) \
                .single() \
                .execute()
            return response.data
        except Exception:
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user from users_insight by ID (auth database)."""
        try:
            response = self.auth_client.table("users_insight") \
                .select("*") \
                .eq("id", user_id) \
                .single() \
                .execute()
            return response.data
        except Exception:
            return None
    
    async def get_user_by_google_id(self, google_id: str) -> Optional[dict]:
        """Get user from users_insight by Google ID (auth database)."""
        try:
            response = self.auth_client.table("users_insight") \
                .select("*") \
                .eq("google_id", google_id) \
                .single() \
                .execute()
            return response.data
        except Exception:
            return None
    
    async def create_user(self, user_data: UserInsightCreate) -> Optional[dict]:
        """Create new user in users_insight (auth database) and sync to main DB."""
        try:
            password_hash = self.hash_password(user_data.password)
            data = {
                "email": user_data.email,
                "password_hash": password_hash,
                "full_name": user_data.full_name,
                "is_admin": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # 1. Create in Auth DB
            response = self.auth_client.table("users_insight").insert(data).execute()
            user = response.data[0] if response.data else None
            
            if user:
                # 2. Sync to Main DB (Critical for FK constraints)
                await self._sync_user_to_main_db(user)
                
            return user
        except Exception as e:
            if settings.debug:
                print(f"Error creating user: {e}")
            return None
    
    async def create_google_user(self, google_info: GoogleUserInfo) -> Optional[dict]:
        """Create user from Google OAuth info (auth database) and sync to main DB."""
        try:
            data = {
                "email": google_info.email,
                "password_hash": "",  # No password for OAuth users
                "full_name": google_info.name,
                "is_admin": False,
                "google_id": google_info.id,
                "oauth_provider": "google",
                "profile_picture": google_info.picture,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # 1. Create in Auth DB
            response = self.auth_client.table("users_insight").insert(data).execute()
            user = response.data[0] if response.data else None
            
            if user:
                # 2. Sync to Main DB (Critical for FK constraints)
                await self._sync_user_to_main_db(user)
                
            return user
        except Exception as e:
            if settings.debug:
                print(f"Error creating Google user: {e}")
            return None

    async def _sync_user_to_main_db(self, user_data: dict) -> bool:
        """
        Synchronize user to Main DB 'users' table.
        This ensures Foreign Key constraints in 'chat_history' and 'expenses' are satisfied.
        """
        try:
            user_id = user_data["id"]
            email = user_data["email"]
            # Use real hash or 'oauth' as placeholder
            password = user_data.get("password_hash") or "oauth_google" 
            
            # Check if user already exists in Main DB with this ID
            existing = self.main_client.table("users").select("id").eq("id", user_id).execute()
            if existing.data:
                return True # Already exists, all good
            
            # Insert with explicit ID to match Auth DB
            main_db_data = {
                "id": user_id,
                "username": email, # Map email to username
                "password": password
            }
            self.main_client.table("users").insert(main_db_data).execute()
            if settings.debug:
                print(f"[SYNC] Synced user {user_id} ({email}) to Main DB")
            return True
        except Exception as e:
            if settings.debug:
                print(f"[SYNC ERROR] Failed to sync user {user_data.get('id')} to Main DB: {e}")
            # Try fallback: Check if username exists but with different ID
            # This is a complex case, but for now we just log the error.
            return False
    
    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp (auth database)."""
        try:
            self.auth_client.table("users_insight") \
                .update({"last_login_at": datetime.now(timezone.utc).isoformat()}) \
                .eq("id", user_id) \
                .execute()
        except Exception:
            pass
    
    async def update_google_info(
        self, 
        user_id: int, 
        google_info: GoogleUserInfo
    ) -> None:
        """Update user's Google OAuth info (auth database)."""
        try:
            self.auth_client.table("users_insight") \
                .update({
                    "google_id": google_info.id,
                    "oauth_provider": "google",
                    "profile_picture": google_info.picture,
                }) \
                .eq("id", user_id) \
                .execute()
        except Exception:
            pass
    
    # ==================== REFRESH TOKEN OPERATIONS ====================
    
    async def store_refresh_token(
        self, 
        user_id: int, 
        token: str, 
        device_info: Optional[str] = None
    ) -> bool:
        """Store refresh token hash in database (main database)."""
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(
                days=settings.jwt_refresh_token_expire_days
            )
            data = {
                "user_id": user_id,
                "token_hash": self.hash_token(token),
                "expires_at": expires_at.isoformat(),
                "device_info": device_info,
                "revoked": False,
            }
            self.main_client.table("refresh_tokens").insert(data).execute()
            return True
        except Exception as e:
            if settings.debug:
                print(f"Error storing refresh token: {e}")
            return False
    
    async def verify_refresh_token(self, token: str, user_id: int) -> bool:
        """Verify refresh token is valid and not revoked (main database)."""
        try:
            token_hash = self.hash_token(token)
            response = self.main_client.table("refresh_tokens") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("token_hash", token_hash) \
                .eq("revoked", False) \
                .single() \
                .execute()
            
            if not response.data:
                return False
            
            # Check expiration
            expires_at = datetime.fromisoformat(
                response.data["expires_at"].replace("Z", "+00:00")
            )
            if datetime.now(timezone.utc) > expires_at:
                return False
            
            return True
        except Exception:
            return False
    
    async def revoke_refresh_token(self, token: str, user_id: int) -> bool:
        """Revoke a refresh token (main database)."""
        try:
            token_hash = self.hash_token(token)
            self.main_client.table("refresh_tokens") \
                .update({"revoked": True}) \
                .eq("user_id", user_id) \
                .eq("token_hash", token_hash) \
                .execute()
            return True
        except Exception:
            return False
    
    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        """Revoke all refresh tokens for a user (main database)."""
        try:
            self.main_client.table("refresh_tokens") \
                .update({"revoked": True}) \
                .eq("user_id", user_id) \
                .execute()
            return True
        except Exception:
            return False
    
    # ==================== GOOGLE OAUTH ====================
    
    def get_google_auth_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    
    async def exchange_google_code(self, code: str) -> Optional[dict]:
        """Exchange authorization code for tokens."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.google_redirect_uri,
                    }
                )
                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None
    
    async def get_google_user_info(self, access_token: str) -> Optional[GoogleUserInfo]:
        """Get user info from Google using access token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return GoogleUserInfo(
                        id=data["id"],
                        email=data["email"],
                        name=data.get("name", data["email"]),
                        picture=data.get("picture"),
                        verified_email=data.get("verified_email", True)
                    )
                return None
        except Exception:
            return None
    
    # ==================== USER SYNC OPERATIONS ====================
    
    async def get_or_create_user_sync(self, user_insight_id: int) -> Optional[dict]:
        """Get or create user expense sync record (main database)."""
        try:
            # Try to get existing sync record
            response = self.main_client.table("user_expense_sync") \
                .select("*") \
                .eq("user_insight_id", user_insight_id) \
                .single() \
                .execute()
            
            if response.data:
                return response.data
            
            # Create new sync record
            data = {
                "user_insight_id": user_insight_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            response = self.main_client.table("user_expense_sync").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception:
            # If table doesn't exist, return None
            return None
    
    def to_user_response(self, user_data: dict) -> UserInsightResponse:
        """Convert database user to response model."""
        return UserInsightResponse(
            id=user_data["id"],
            email=user_data["email"],
            full_name=user_data.get("full_name", ""),
            is_admin=user_data.get("is_admin", False),
            profile_picture=user_data.get("profile_picture"),
            oauth_provider=user_data.get("oauth_provider"),
            created_at=user_data.get("created_at"),
            last_login_at=user_data.get("last_login_at"),
        )
