"""
NEXUS -- Application Configuration.

Loads settings from environment variables / ``.env`` file using Pydantic
Settings. Every configuration variable defined in ``.env.example`` is mapped here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Central configuration -- all values can be overridden via env vars."""

    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- PostgreSQL (asyncpg driver) ------------------------------------------
    # Loaded directly from .env (DATABASE_URL)
    database_url: str = ""

    # -- Google Gemini API ----------------------------------------------------
    # Loaded directly from .env (GEMINI_API_KEY)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # -- JWT Authentication ---------------------------------------------------
    # Loaded directly from .env (JWT_SECRET_KEY)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # -- Upload limits --------------------------------------------------------
    max_resume_upload_bytes: int = 10485760  # 10 MB
    upload_dir: Path = _BACKEND_DIR / "uploads"

    # -- HeyGen API (optional -- falls back to Edge-TTS if empty) -------------
    # Loaded directly from .env (HEYGEN_API_KEY)
    heygen_api_key: str = ""

    # -- D-ID API (optional free-tier avatar video alternative) ---------------
    # Loaded directly from .env (DID_API_KEY, DID_AVATAR_ID)
    did_api_key: str = ""
    did_avatar_id: str = "public_mia_elegant@avt_TJ0Tq5"

    # -- Adzuna API (optional free developer keys with mandatory salary data) --
    # Loaded directly from .env (ADZUNA_APP_ID, ADZUNA_APP_KEY)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # -- Email & Password Reset (Gmail SMTP) ----------------------------------
    # Loaded directly from .env (GMAIL_USER, GMAIL_APP_PASSWORD, FRONTEND_URL)
    gmail_user: str = ""
    gmail_app_password: str = ""
    frontend_url: str = "http://localhost:3000"
    password_reset_expire_minutes: int = 10  # 10 minutes max per security policy
    email_verification_expire_minutes: int = 1440  # 24 hours

    # -- Scraping politeness --------------------------------------------------
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0

    # -- Scheduled Cron Security Token ----------------------------------------
    # If set, calls to /api/system/cron-run must provide this secret token
    cron_secret: str = ""

    # -- Google OAuth 2.0 (Sign-In) -------------------------------------------
    # Loaded directly from .env (GOOGLE_CLIENT_ID)
    google_client_id: str = ""

    # -- Logging level (DEBUG | INFO | WARNING | ERROR) -----------------------
    log_level: str = "INFO"

    # -- Paths & CORS Defaults ------------------------------------------------
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    project_root: Path = _BACKEND_DIR

    @property
    def all_cors_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        if self.frontend_url:
            clean = self.frontend_url.rstrip("/")
            if clean and clean not in origins:
                origins.append(clean)
        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
