"""
NEXUS -- Application Configuration.

Loads settings from environment variables / ``.env`` file using Pydantic
Settings.  Every knob that changes between environments lives here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration -- all values can be overridden via env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- Database -------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus"

    # -- Google Gemini --------------------------------------------------------
    gemini_api_key: str = ""

    # -- JWT Authentication ---------------------------------------------------
    jwt_secret_key: str = "CHANGE-ME-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # -- File Uploads ---------------------------------------------------------
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    max_resume_upload_bytes: int = 10 * 1024 * 1024

    # -- Video Briefing -------------------------------------------------------
    heygen_api_key: str = ""  # optional; falls back to Edge-TTS if empty

    # -- CORS -----------------------------------------------------------------
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # -- Scraping -------------------------------------------------------------
    scrape_delay_min: float = 2.0
    scrape_delay_max: float = 5.0

    # -- Logging --------------------------------------------------------------
    log_level: str = "INFO"

    # -- Paths ----------------------------------------------------------------
    project_root: Path = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
