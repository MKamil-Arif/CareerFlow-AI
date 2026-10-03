"""Application settings, read once from environment variables.

Local development: put values in a `.env` file at the repository root.
Hosted deployments (Render, Hugging Face Spaces, Docker): set the same
variables in the platform's environment/secrets settings instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_DIR = Path(__file__).resolve().parent / "data"

# Repository-root .env first; the old backend/app/.env location still works.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development").lower())
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", "").strip())
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip())
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip())
    ai_timeout_seconds: int = field(default_factory=lambda: _int("AI_TIMEOUT_SECONDS", 25))

    # Comma-separated list of extra origins allowed to call the API (only needed
    # when the frontend is hosted on a different domain than the API).
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS"))

    max_upload_mb: int = field(default_factory=lambda: _int("MAX_UPLOAD_MB", 5))
    # Requests per minute, per client IP. 0 disables the limit.
    rate_limit_ai_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_AI_PER_MINUTE", 20))
    rate_limit_default_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_DEFAULT_PER_MINUTE", 120))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def ai_configured(self) -> bool:
        return bool(self.groq_api_key or self.gemini_api_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
