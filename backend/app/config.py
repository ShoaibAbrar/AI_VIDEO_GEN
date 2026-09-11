"""
Application configuration from environment variables.
"""

import os
import secrets
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Get the backend directory
BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / "backend" / ".env")


class Settings:
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Wan2GP Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./wangp.db"
    )
    
    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # Storage
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", str(BASE_DIR / "generated_videos"))

    # Wan2GP runtime and worker
    WAN2GP_ROOT: str = os.getenv("WAN2GP_ROOT", str(BASE_DIR))
    WAN2GP_CONFIG_PATH: str = os.getenv("WAN2GP_CONFIG_PATH", "")
    GENERATION_WORKER_POLL_SECONDS: float = float(os.getenv("GENERATION_WORKER_POLL_SECONDS", "1.0"))
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        """Ensure storage path exists."""
        Path(self.STORAGE_PATH).mkdir(parents=True, exist_ok=True)


settings = Settings()
