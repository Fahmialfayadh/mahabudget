"""
Configuration management for Dompet Curhat application.
Centralized settings with environment variable validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration (Main SIBudget Database)
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
    # Auth Supabase Configuration (users_insight Database)
    auth_supabase_url: str
    auth_supabase_key: str
    auth_supabase_service_key: str
    
    # Groq Configuration
    groq_api_key: str
    
    # App Configuration
    debug: bool = False
    
    # AI Model Configuration
    accountant_model: str = "llama-3.1-8b-instant"
    bestie_model: str = "llama-3.3-70b-versatile"
    scanner_model: str = "llama-3.2-11b-vision-preview"
    
    # Storage Configuration
    receipt_bucket: str = "receipts"
    max_image_size_mb: int = 5
    
    # JWT Configuration
    secret_key: str
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    
    # CORS Configuration
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"
    
    # Google OAuth Configuration
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
